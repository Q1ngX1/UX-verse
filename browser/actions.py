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


class Scroll(BrowserAction):
    type: Literal["scroll"] = "scroll"
    dx: int = 0
    dy: int = 0


class TypeText(PointerAction):
    type: Literal["type"] = "type"
    text: Annotated[str, Field(min_length=1, max_length=1000)]


class Back(BrowserAction):
    type: Literal["back"] = "back"


class Wait(BrowserAction):
    type: Literal["wait"] = "wait"
    ms: Annotated[int, Field(ge=0, le=2000)]


Action = Annotated[Navigate | Click | Hover | Scroll | TypeText | Back | Wait, Field(discriminator="type")]
MAX_STEPS = 30
ACTION_LIST = TypeAdapter(Annotated[list[Action], Field(max_length=MAX_STEPS - 1)])
