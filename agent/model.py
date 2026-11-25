from dataclasses import dataclass
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from browser.actions import Click, Hover, KeyText, PressKey, Scroll, Swipe, Tap, Wait
from browser.input_devices import Device
from models.contracts import ModelError as ModelError, ModelUsage as ModelUsage, RetryableModelError as RetryableModelError

Mode = Literal["task", "explore"]
DesktopAction = Annotated[Click | Hover | Scroll | KeyText | PressKey | Wait, Field(discriminator="type")]
MobileAction = Annotated[Tap | Swipe | KeyText | Wait, Field(discriminator="type")]
ExplorerAction = DesktopAction | MobileAction


class DecisionBase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, str_strip_whitespace=True)

    reason: Annotated[str, Field(min_length=1, max_length=500)]


class Act(DecisionBase):
    type: Literal["act"]
    action: ExplorerAction


class Stop(DecisionBase):
    type: Literal["stop"]
    outcome: Literal["completed", "gave_up"]
    answer: Annotated[str, Field(min_length=1, max_length=1000)] | None = None


class DesktopAct(Act):
    action: DesktopAction


class MobileAct(Act):
    action: MobileAction


Decision = Annotated[Act | Stop, Field(discriminator="type")]
DECISION = TypeAdapter(Decision)
DEVICE_DECISIONS = {
    "desktop": TypeAdapter(Annotated[DesktopAct | Stop, Field(discriminator="type")]),
    "mobile": TypeAdapter(Annotated[MobileAct | Stop, Field(discriminator="type")]),
}


@dataclass(frozen=True)
class Observation:
    screenshot_png: bytes
    width: int
    height: int


@dataclass(frozen=True)
class HistoryEntry:
    action: ExplorerAction
    visual_change: bool
    visual_cycle: bool = False


@dataclass(frozen=True)
class DecisionRequest:
    task: str
    persona: str | None
    observation: Observation
    history: tuple[HistoryEntry, ...]
    steps_remaining: int
    retry_feedback: str | None = None
    mode: Mode = "task"
    device: Device = "desktop"


@dataclass(frozen=True)
class ModelReply:
    decision_json: str
    usage: ModelUsage | None = None
    model_id: str | None = None


class ExplorerModel(Protocol):
    async def decide(self, request: DecisionRequest) -> ModelReply:
        """Use the screenshot and task to return a decision matching DECISION.json_schema()."""
        ...
