from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter


class BrowserAction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Navigate(BrowserAction):
    type: Literal["navigate"] = "navigate"
    url: HttpUrl


class PointerAction(BrowserAction):
    x: Annotated[int, Field(ge=0)]
    y: Annotated[int, Field(ge=0)]


class Click(PointerAction):
    type: Literal["click"] = "click"


class Hover(PointerAction):
    type: Literal["hover"] = "hover"


class Tap(PointerAction):
    type: Literal["tap"] = "tap"


class Swipe(PointerAction):
    type: Literal["swipe"] = "swipe"
    end_x: Annotated[int, Field(ge=0)]
    end_y: Annotated[int, Field(ge=0)]


class Scroll(BrowserAction):
    type: Literal["scroll"] = "scroll"
    dx: int = 0
    dy: int = 0


class CenterReading(PointerAction):
    """Bring a visible reading point toward the middle of the viewport."""

    type: Literal["center_reading"] = "center_reading"

    def vertical_offset(self, viewport_height: int) -> int:
        offset = self.y - viewport_height // 2
        return offset if abs(offset) > viewport_height * 0.15 else 0


class TypeText(PointerAction):
    type: Literal["type"] = "type"
    text: Annotated[str, Field(min_length=1, max_length=1000)]


class KeyText(TypeText):
    """Printable ASCII that Chromium can enter with keyboard events."""

    text: Annotated[str, Field(min_length=1, max_length=1000, pattern=r"^[ -~]+$")]


class Back(BrowserAction):
    type: Literal["back"] = "back"


class PressKey(BrowserAction):
    type: Literal["key"] = "key"
    key: Literal["Tab", "Shift+Tab", "Escape", "ArrowUp", "ArrowDown", "Enter"]


class FindText(BrowserAction):
    type: Literal["find"] = "find"
    text: Annotated[str, Field(min_length=1, max_length=200)]
    links_only: bool = False


class Wait(BrowserAction):
    type: Literal["wait"] = "wait"
    ms: Annotated[int, Field(ge=0, le=2000)]


Action = Annotated[
    Navigate | Click | Hover | Tap | Swipe | Scroll | CenterReading | TypeText | Back | PressKey | FindText | Wait,
    Field(discriminator="type"),
]
MAX_STEPS = 30
ACTION_LIST = TypeAdapter(Annotated[list[Action], Field(max_length=MAX_STEPS - 1)])
