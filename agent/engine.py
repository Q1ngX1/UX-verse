import asyncio
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Literal
from uuid import uuid4

from playwright.async_api import Error as BrowserError
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError

from browser.actions import MAX_STEPS, Navigate, PointerAction
from browser.worker import RUN_TIMEOUT, VIEWPORT, BrowserWorker, PageObservation, browser_worker
from logs import EventSink, RunEvents

from .model import (
    DECISION,
    Act,
    Decision,
    DecisionRequest,
    ExplorerModel,
    HistoryEntry,
    ModelError,
    ModelReply,
    Observation,
    RetryableModelError,
    Stop,
)

MODEL_TIMEOUT = 15


class AgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    target: HttpUrl
    task: str = Field(min_length=1, max_length=2000)
    persona: str | None = Field(default=None, min_length=1, max_length=1000)
    max_steps: int = Field(default=12, ge=1, lt=MAX_STEPS, strict=True)
    timeout_seconds: float = Field(default=RUN_TIMEOUT, gt=0, le=RUN_TIMEOUT)
    model_timeout_seconds: float = Field(default=MODEL_TIMEOUT, gt=0, le=RUN_TIMEOUT)


Status = Literal["completed", "gave_up", "step_limit", "model_error", "browser_error", "timeout"]


@dataclass(frozen=True)
class AgentResult:
    status: Status
    reason: str
    steps: int
    model_calls: int


class _Run:
    def __init__(self, config: AgentConfig, model: ExplorerModel, output: Path, emit: EventSink) -> None:
        self.config = config
        self.model = model
        self.output = output
        self.record = emit
        self.steps = 0
        self.model_calls = 0

    async def decide(
        self, request: DecisionRequest, page: PageObservation, *, decision_id: str, action_id: str,
    ) -> Decision:
        for attempt in (1, 2):
            self.model_calls += 1
            fields: dict[str, object] = {
                "call": self.model_calls,
                "attempt": attempt,
                "after_steps": self.steps,
                "decision_id": decision_id,
                "observation_id": page["observation_id"],
            }
            self.record("model_requested", **fields, observation=page)
            try:
                async with asyncio.timeout(self.config.model_timeout_seconds):
                    reply = await self.model.decide(request)
                if not isinstance(reply, ModelReply):
                    raise ModelError("The adapter must return ModelReply.")
            except (RetryableModelError, TimeoutError) as error:
                if isinstance(error, ModelError) and error.http_status is not None:
                    fields["http_status"] = error.http_status
                self.record("model_error", **fields, error=type(error).__name__)
                feedback = "The previous model call failed or timed out. Try again."
            except ModelError as error:
                if error.http_status is not None:
                    fields["http_status"] = error.http_status
                self.record("model_error", **fields, error=type(error).__name__)
                raise
            except Exception as error:
                self.record("model_error", **fields, error=type(error).__name__)
                raise ModelError(f"The model adapter failed ({type(error).__name__}).") from error
            else:
                usage = asdict(reply.usage) if reply.usage is not None else None
                if reply.model_id is not None:
                    fields["model_id"] = reply.model_id
                try:
                    decision = DECISION.validate_json(reply.decision_json)
                    if isinstance(decision, Act) and isinstance(decision.action, PointerAction):
                        pointer = decision.action
                        if pointer.x >= request.observation.width or pointer.y >= request.observation.height:
                            raise ValueError("Pointer coordinates must be inside the screenshot.")
                except ValidationError as error:
                    issues = [
                        {"location": item["loc"], "type": item["type"]}
                        for item in error.errors(include_url=False, include_context=False, include_input=False)
                    ]
                    self.record("invalid_decision", **fields, error=type(error).__name__, issues=issues, usage=usage)
                    feedback = "Return a decision matching the schema. Validation errors: " + ", ".join(
                        f"{'.'.join(map(str, item['location'])) or 'decision'} ({item['type']})" for item in issues
                    )
                except ValueError as error:
                    self.record("invalid_decision", **fields, error=type(error).__name__, usage=usage)
                    feedback = "Return a decision matching the schema, with any pointer inside the screenshot."
                else:
                    if isinstance(decision, Act) and request.steps_remaining > 0:
                        fields["action_id"] = action_id
                    self.record("model_decision", **fields, decision=decision.model_dump(mode="json"), usage=usage)
                    return decision
            request = replace(request, retry_feedback=feedback)
        raise ModelError(feedback)

    def observe(self, page: PageObservation) -> Observation:
        return Observation(
            url=page["url"],
            title=page["title"],
            screenshot_png=(self.output / page["screenshot"]).read_bytes(),
            width=VIEWPORT["width"],
            height=VIEWPORT["height"],
        )

    async def explore(self, worker: BrowserWorker) -> tuple[Status, str]:
        page = await worker.execute(Navigate(url=self.config.target))
        history: list[HistoryEntry] = []
        while True:
            remaining = self.config.max_steps - self.steps
            request = DecisionRequest(
                task=self.config.task,
                persona=self.config.persona,
                observation=self.observe(page),
                history=tuple(history),
                steps_remaining=remaining,
            )
            decision_id, action_id = uuid4().hex, uuid4().hex
            decision = await self.decide(request, page, decision_id=decision_id, action_id=action_id)
            if isinstance(decision, Stop):
                return decision.outcome, decision.reason
            if remaining == 0:
                return "step_limit", "The action budget was exhausted."
            self.steps += 1
            page = await worker.execute(decision.action, action_id=action_id, decision_id=decision_id)
            history.append(HistoryEntry(decision.action, page["url"], page["title"]))


async def run_agent(
    config: AgentConfig, model: ExplorerModel, output: Path, *, headed: bool = False,
) -> AgentResult:
    """Run one Explorer in its own browser session and write the decision and browser logs."""
    events = RunEvents()
    async with browser_worker(config.target, output, headed=headed, events=events) as worker:
        with events.open_log(output / "agent.jsonl", source="agent") as emit:
            run = _Run(config, model, output, emit)
            run.record("run_started", config=config.model_dump(mode="json"))
            try:
                async with asyncio.timeout(config.timeout_seconds):
                    status, reason = await run.explore(worker)
            except ModelError as error:
                status, reason = "model_error", str(error)
            except TimeoutError:
                status, reason = "timeout", "The run or browser action reached its time limit."
            except (BrowserError, OSError, ValueError) as error:
                status, reason = "browser_error", str(error)
            result = AgentResult(status, reason, run.steps, run.model_calls)
            run.record("run_finished", **asdict(result))
            return result
