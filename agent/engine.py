import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Literal
from uuid import uuid4

from playwright.async_api import Error as BrowserError, Page
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError, model_validator

from browser.actions import MAX_STEPS, Click, Navigate, PointerAction, Scroll, Swipe, Tap, TypeText
from browser.input_devices import Device
from browser.viewport import Viewport
from browser.worker import RUN_TIMEOUT, BrowserWorker, PageObservation, browser_worker
from logs import EventSink, RunEvents

from .model import (
    DEVICE_DECISIONS,
    Act,
    Decision,
    DecisionRequest,
    ExplorerModel,
    HistoryEntry,
    ModelError,
    ModelReply,
    Mode,
    Observation,
    RetryableModelError,
    Stop,
)

MODEL_TIMEOUT = 15
MAX_RUN_TIMEOUT = 300


class AgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    target: HttpUrl
    task: str | None = Field(default=None, min_length=1, max_length=2000)
    persona: str | None = Field(default=None, min_length=1, max_length=1000)
    max_steps: int = Field(default=12, ge=1, lt=MAX_STEPS, strict=True)
    timeout_seconds: float = Field(default=RUN_TIMEOUT, gt=0, le=MAX_RUN_TIMEOUT)
    model_timeout_seconds: float = Field(default=MODEL_TIMEOUT, gt=0, le=MAX_RUN_TIMEOUT)
    record_input: bool = False
    viewport: Viewport = Viewport()
    pointer_mode: Literal["continuous"] = "continuous"
    mode: Mode = "task"
    device: Device = "desktop"

    @model_validator(mode="after")
    def require_task_for_task_mode(self) -> "AgentConfig":
        if self.mode == "task" and self.task is None:
            raise ValueError("Task mode requires a task.")
        return self


Status = Literal["completed", "gave_up", "stalled", "step_limit", "model_error", "browser_error", "timeout"]


@dataclass(frozen=True)
class AgentResult:
    status: Status
    reason: str
    steps: int
    model_calls: int
    answer: str | None = None


class NoProgress(Exception):
    """The model repeated an action after being asked to change course."""


def _repetition_feedback(decision: Decision, request: DecisionRequest) -> str | None:
    if not isinstance(decision, Act) or len(request.history) < 2 or request.steps_remaining == 0:
        return None
    previous, latest = request.history[-2:]
    action = decision.action
    unchanged = not (previous.visual_change or latest.visual_change)
    if (isinstance(action, TypeText) and action == previous.action == latest.action
            and not latest.visual_change):
        return "The screenshot did not change after repeating the text entry. Reassess the visible controls."
    if isinstance(action, Click) and isinstance(previous.action, Click) and isinstance(latest.action, Click):
        if all(abs(item.x - action.x) <= 12 and abs(item.y - action.y) <= 12
               for item in (previous.action, latest.action)):
            if latest.visual_cycle:
                return "Two clicks returned to an earlier screenshot. Inspect the current view before repeating."
            if unchanged:
                return "Two clicks at this point had no visible effect. Choose another control, type into a search field, or scroll to find the right link."
    if unchanged and isinstance(action, Scroll) and action == previous.action == latest.action:
        return ("The last two identical scrolls left the screenshot unchanged. Try a different control or direction: "
                "use positive dy to reveal content farther down, negative dy to return toward the top.")
    if unchanged and isinstance(action, (Tap, Swipe)) and action == previous.action == latest.action:
        return "The last two identical gestures had no visible effect. Try a different control or gesture."
    return None


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
            self.record("model_requested", **fields, observation={
                "observation_id": page["observation_id"], "screenshot": page["screenshot"],
            })
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
                    decision = DEVICE_DECISIONS[request.device].validate_json(reply.decision_json)
                    if isinstance(decision, Act):
                        action = decision.action
                        width, height = request.observation.width, request.observation.height
                        if isinstance(action, PointerAction) and (action.x >= width or action.y >= height):
                            raise ValueError("Pointer coordinates must be inside the screenshot.")
                        if isinstance(action, Swipe) and (action.end_x >= width or action.end_y >= height):
                            raise ValueError("Swipe endpoint must be inside the screenshot.")
                    elif request.mode == "explore" and decision.outcome == "completed" and decision.answer is None:
                        raise ValueError("Completed exploration requires a short summary of observations.")
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
                    feedback = str(error)
                else:
                    repeated = _repetition_feedback(decision, request)
                    if repeated:
                        self.record("repeated_action", **fields, decision=decision.model_dump(mode="json"), usage=usage)
                        if attempt == 2:
                            raise NoProgress(repeated)
                        request = replace(request, retry_feedback=repeated)
                        continue
                    if isinstance(decision, Act) and request.steps_remaining > 0:
                        fields["action_id"] = action_id
                    self.record("model_decision", **fields, decision=decision.model_dump(mode="json"), usage=usage)
                    return decision
            request = replace(request, retry_feedback=feedback)
        raise ModelError(feedback)

    def observe(self, page: PageObservation) -> Observation:
        return Observation(
            screenshot_png=(self.output / page["screenshot"]).read_bytes(),
            width=page["viewport"]["width"],
            height=page["viewport"]["height"],
        )

    async def explore(self, worker: BrowserWorker) -> tuple[Status, str, str | None]:
        page = await worker.execute(Navigate(url=self.config.target))
        history: list[HistoryEntry] = []
        while True:
            remaining = self.config.max_steps - self.steps
            request = DecisionRequest(
                task=self.config.task or "Explore the site's visible navigation and describe what you observed.",
                persona=self.config.persona,
                observation=self.observe(page),
                history=tuple(history),
                steps_remaining=remaining,
                mode=self.config.mode,
                device=self.config.device,
            )
            decision_id, action_id = uuid4().hex, uuid4().hex
            decision = await self.decide(request, page, decision_id=decision_id, action_id=action_id)
            if isinstance(decision, Stop):
                return decision.outcome, decision.reason, decision.answer
            if remaining == 0:
                return "step_limit", "The action budget was exhausted.", None
            self.steps += 1
            page = await worker.execute(
                decision.action, action_id=action_id, decision_id=decision_id, recover_rejection=True,
            )
            effect = page.get("effect")
            history.append(HistoryEntry(
                decision.action,
                visual_change=effect is not None and effect["visual_change"],
                visual_cycle=effect is not None and effect.get("visual_cycle", False),
            ))


async def run_agent(
    config: AgentConfig, model: ExplorerModel, output: Path, *, headed: bool = False,
    inspect_final: Callable[[Page], Awaitable[None]] | None = None,
) -> AgentResult:
    """Run one Explorer in its own browser session and write the decision and browser logs."""
    events = RunEvents()
    async with browser_worker(
        config.target, output, headed=headed, events=events, inspect_final=inspect_final,
        timeout_seconds=config.timeout_seconds, record_input=config.record_input,
        pointer_mode=config.pointer_mode, human_input=True, viewport=config.viewport, device=config.device,
    ) as worker:
        with events.open_log(output / "agent.jsonl", source="agent") as emit:
            run = _Run(config, model, output, emit)
            run.record("run_started", config=config.model_dump(mode="json"))
            answer = None
            try:
                async with asyncio.timeout(config.timeout_seconds):
                    status, reason, answer = await run.explore(worker)
            except ModelError as error:
                status, reason = "model_error", str(error)
            except NoProgress as error:
                status, reason = "stalled", str(error)
            except TimeoutError:
                status, reason = "timeout", "The run or browser action reached its time limit."
            except (BrowserError, OSError, ValueError) as error:
                status, reason = "browser_error", str(error)
            result = AgentResult(status, reason, run.steps, run.model_calls, answer)
            run.record("run_finished", **asdict(result))
            return result
