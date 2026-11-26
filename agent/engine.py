import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from random import randint
from time import perf_counter
from typing import Literal
from uuid import uuid4

from playwright.async_api import Error as BrowserError, Page
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError, model_validator

from browser.actions import MAX_STEPS, CenterReading, Click, Navigate, PointerAction, Scroll, Swipe, Tap, TypeText
from browser.input_devices import REACTION_TIME_MS, ContinuousPointerMode, Device
from browser.touch_motion import TouchMotion
from browser.viewport import Viewport
from browser.worker import RUN_TIMEOUT, ActionEffect, BrowserWorker, PageObservation, browser_worker
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
MAX_SCROLL_AXIS = 2400
THOUGHT_TIME_MS = (750, 1100)
READING_THRESHOLD_WORDS = 48
MAX_READING_TIME_MS = 10_000


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
    pointer_mode: ContinuousPointerMode = "continuous"
    mode: Mode = "task"
    device: Device = "desktop"
    touch_motion: TouchMotion = "linear"
    touch_seed: int = 0

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
    if not isinstance(decision, Act) or not request.history or request.steps_remaining == 0:
        return None
    action = decision.action
    latest = request.history[-1]
    if isinstance(action, CenterReading) and isinstance(latest.action, CenterReading):
        return "The reading position was already adjusted once. Read from the current screenshot or choose another action."
    if len(request.history) < 2:
        return None
    previous = request.history[-2]
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


def _position_before_answer(decision: Decision, request: DecisionRequest) -> Decision:
    if (not isinstance(decision, Stop) or decision.outcome != "completed" or not decision.answer
            or decision.reading_point is None or request.steps_remaining == 0
            or (request.history and isinstance(request.history[-1].action, CenterReading))):
        return decision
    point = decision.reading_point
    width, height = request.observation.width, request.observation.height
    if point.x >= width or point.y >= height:
        raise ValueError("The reading point must be inside the screenshot.")
    action = CenterReading(x=point.x, y=point.y)
    if not action.vertical_offset(height):
        return decision
    return Act(type="act", reason="Position the answer's source before reading.", action=action)


def _position_after_edge_activation(
    decision: Decision, request: DecisionRequest, effect: ActionEffect | None,
) -> Act | None:
    if (not isinstance(decision, Act) or not isinstance(decision.action, (Click, Tap))
            or not request.history or not request.steps_remaining or effect is None or effect["url_changed"]):
        return None
    latest = request.history[-1]
    previous = latest.action
    action = decision.action
    height = request.observation.height
    if (not isinstance(previous, (Click, Tap)) or previous.type != action.type
            or not latest.visual_change or latest.visual_cycle or previous.y < height * 0.85
            or abs(previous.x - action.x) > 12 or abs(previous.y - action.y) > 12):
        return None
    # The first activation changed the view. Bring the area just below it into view before activating it again.
    point = CenterReading(x=previous.x, y=min(height - 1, previous.y + round(height * 0.05)))
    return Act(type="act", reason="Inspect the changed area below the last activation.", action=point)


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
                    decision = _position_before_answer(decision, request)
                    if isinstance(decision, Act):
                        action = decision.action
                        width, height = request.observation.width, request.observation.height
                        if isinstance(action, PointerAction) and (action.x >= width or action.y >= height):
                            raise ValueError("Pointer coordinates must be inside the screenshot.")
                        if isinstance(action, Swipe) and (action.end_x >= width or action.end_y >= height):
                            raise ValueError("Swipe endpoint must be inside the screenshot.")
                        if isinstance(action, Scroll) and max(abs(action.dx), abs(action.dy)) > MAX_SCROLL_AXIS:
                            raise ValueError(
                                f"Use multiple scrolls for long distances. Each axis allows up to {MAX_SCROLL_AXIS} pixels per action."
                            )
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
                    adjustment = _position_after_edge_activation(decision, request, page.get("effect"))
                    if adjustment is not None:
                        self.record("action_adjusted", **fields, action_id=action_id,
                                    proposed=decision.model_dump(mode="json"), adjusted=adjustment.model_dump(mode="json"))
                        decision = adjustment
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
        read_views: set[tuple[str, str]] = set()
        refreshed_after_idle = False
        while True:
            observed_at = perf_counter()
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
            if isinstance(decision, Act) and remaining == 0:
                return "step_limit", "The action budget was exhausted.", None

            reading = page.get("reading")
            read_words = 0
            adjusting = isinstance(decision, Act) and isinstance(decision.action, CenterReading)
            if not adjusting and reading is not None and reading["words"] >= READING_THRESHOLD_WORDS:
                key = (page["url"], reading["key"])
                if key not in read_views:
                    read_words = reading["words"]
                    read_views.add(key)
            target_ms = randint(*REACTION_TIME_MS) if isinstance(decision, Act) else 0
            thought_ms = randint(*THOUGHT_TIME_MS) if isinstance(decision, Act) else 0
            # Simulate scanning a portion of the visible prose, with a budget for long pages.
            reading_ms = 0
            if read_words:
                reading_ms = min(MAX_READING_TIME_MS, round(read_words * 0.30 * 60_000 / randint(210, 260)))
            attention_ms = max(target_ms, thought_ms, reading_ms)
            ready_at = observed_at + attention_ms / 1000
            wait_started = perf_counter()
            moved, refreshed = False, None
            if (delay := ready_at - wait_started) > 0:
                moved, refreshed = await worker.idle(
                    delay, page=page, decision_id=decision_id, reading=bool(read_words),
                    wander=bool(read_words) and not refreshed_after_idle,
                )
            ready = perf_counter()
            added_wait_ms = round((ready - wait_started) * 1000, 1) if wait_started < ready_at else 0
            if attention_ms:
                self.record("attention_timing", decision_id=decision_id, observation_id=page["observation_id"],
                            activity="reading" if read_words else "thinking", visible_words=read_words,
                            target_ms=attention_ms, added_wait_ms=added_wait_ms, idle_mouse_moved=moved)
            if refreshed is not None:
                self.record("decision_superseded", decision_id=decision_id, observation_id=page["observation_id"],
                            next_observation_id=refreshed["observation_id"])
                page = refreshed
                refreshed_after_idle = True
                continue
            if isinstance(decision, Stop):
                return decision.outcome, decision.reason, decision.answer
            self.record("reaction_timing", action_id=action_id, decision_id=decision_id,
                        observation_id=page["observation_id"], target_ms=target_ms,
                        observation_to_action_ms=round((ready - observed_at) * 1000, 1),
                        added_wait_ms=added_wait_ms)
            self.steps += 1
            page = await worker.execute(
                decision.action, action_id=action_id, decision_id=decision_id, recover_rejection=True,
            )
            refreshed_after_idle = False
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
        touch_motion=config.touch_motion, touch_seed=config.touch_seed,
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
