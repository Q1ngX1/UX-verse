from dataclasses import dataclass
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from browser.actions import Back, Click, Hover, Scroll, TypeText, Wait
from models.contracts import ModelError as ModelError, ModelUsage as ModelUsage, RetryableModelError as RetryableModelError

ExplorerAction = Annotated[Click | Hover | Scroll | TypeText | Back | Wait, Field(discriminator="type")]


class DecisionBase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, str_strip_whitespace=True)

    reason: Annotated[str, Field(min_length=1, max_length=500)]


class Act(DecisionBase):
    type: Literal["act"]
    action: ExplorerAction


class Stop(DecisionBase):
    type: Literal["stop"]
    outcome: Literal["completed", "gave_up"]


Decision = Annotated[Act | Stop, Field(discriminator="type")]
DECISION = TypeAdapter(Decision)


@dataclass(frozen=True)
class Observation:
    url: str
    title: str
    screenshot_png: bytes
    width: int
    height: int


@dataclass(frozen=True)
class HistoryEntry:
    action: ExplorerAction
    url: str
    title: str


@dataclass(frozen=True)
class DecisionRequest:
    task: str
    persona: str | None
    observation: Observation
    history: tuple[HistoryEntry, ...]
    steps_remaining: int
    retry_feedback: str | None = None


@dataclass(frozen=True)
class ModelReply:
    decision_json: str
    usage: ModelUsage | None = None
    model_id: str | None = None


class ExplorerModel(Protocol):
    async def decide(self, request: DecisionRequest) -> ModelReply:
        """Use the screenshot and task to return a decision matching DECISION.json_schema()."""
        ...
