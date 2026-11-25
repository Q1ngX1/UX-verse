"""Page-scoped input devices for browser actions."""

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from math import hypot
from typing import Literal

from playwright.async_api import CDPSession, Keyboard, Mouse, Touchscreen

Device = Literal["desktop", "mobile"]
PointerMode = Literal["direct", "continuous"]
TextInputMode = Literal["insert", "sequential"]
Dispatch = Callable[..., Awaitable[None]]
Point = tuple[int, int]
Trajectory = Callable[[Point, Point], Iterable[tuple[Point, float]]]
_SHIFTED_KEYS = dict(zip(
    "~!@#$%^&*()_+{}|:\"<>?",
    ("Backquote", "Digit1", "Digit2", "Digit3", "Digit4", "Digit5", "Digit6", "Digit7", "Digit8",
     "Digit9", "Digit0", "Minus", "Equal", "BracketLeft", "BracketRight", "Backslash", "Semicolon",
     "Quote", "Comma", "Period", "Slash"),
))


def smooth_trajectory(start: Point, target: Point) -> Iterable[tuple[Point, float]]:
    """Yield eased positions and the seconds to wait before each move."""
    dx, dy = target[0] - start[0], target[1] - start[1]
    distance = hypot(dx, dy)
    steps = min(24, max(4, round(distance / 25)))
    interval = min(0.36, max(0.08, distance / 2800)) / steps
    for step in range(1, steps + 1):
        t = step / steps
        fraction = t * t * (3 - 2 * t)
        yield (round(start[0] + dx * fraction), round(start[1] + dy * fraction)), interval


class VirtualMouse:
    def __init__(self, backend: Mouse, dispatch: Dispatch, trajectory: Trajectory | None = None) -> None:
        self._backend = backend
        self._dispatch = dispatch
        self._trajectory = trajectory
        self.position: Point = (0, 0)

    async def _move(self, point: Point) -> None:
        await self._dispatch("mouse.move", self._backend.move, *point)
        self.position = point

    async def move(self, x: int, y: int) -> None:
        target = (x, y)
        if self._trajectory is None:
            await self._move(target)
            return
        if target != self.position:
            for point, delay in self._trajectory(self.position, target):
                await asyncio.sleep(delay)
                if point != self.position:
                    await self._move(point)
            if target != self.position:
                await self._move(target)

    async def prepare_click(self, x: int, y: int) -> None:
        if self._trajectory is not None:
            await self.move(x, y)

    async def click(self, x: int, y: int) -> None:
        await self.prepare_click(x, y)
        await self._dispatch("mouse.click", self._backend.click, x, y)
        self.position = (x, y)

    async def wheel(self, dx: int, dy: int) -> None:
        await self._dispatch("mouse.wheel", self._backend.wheel, dx, dy)


class VirtualTouchscreen:
    def __init__(self, backend: Touchscreen, session: CDPSession, dispatch: Dispatch) -> None:
        self._backend = backend
        self._session = session
        self._dispatch = dispatch

    async def tap(self, x: int, y: int) -> None:
        await self._dispatch("touchscreen.tap", self._backend.tap, x, y)

    async def _touch(self, event: str, points: list[dict[str, int]]) -> None:
        await self._dispatch("Input.dispatchTouchEvent", self._session.send, "Input.dispatchTouchEvent",
                             {"type": event, "touchPoints": points})

    async def swipe(self, start: Point, end: Point) -> None:
        await self._touch("touchStart", [{"x": start[0], "y": start[1]}])
        try:
            for (x, y), delay in smooth_trajectory(start, end):
                await asyncio.sleep(delay)
                await self._touch("touchMove", [{"x": x, "y": y}])
        finally:
            await self._touch("touchEnd", [])


class VirtualKeyboard:
    def __init__(self, backend: Keyboard, dispatch: Dispatch, text_mode: TextInputMode = "insert") -> None:
        self._backend = backend
        self._dispatch = dispatch
        self._text_mode = text_mode

    async def press(self, key: str) -> None:
        await self._dispatch("keyboard.press", self._backend.press, key)

    async def type_keys(self, text: str) -> None:
        if not text.isascii() or not text.isprintable():
            raise ValueError("Keyboard-only text must be printable ASCII.")
        for character in text:
            if character in _SHIFTED_KEYS:
                key = f"Shift+{_SHIFTED_KEYS[character]}"
            elif character.isupper():
                key = f"Shift+Key{character}"
            else:
                key = "Space" if character == " " else character
            await self.press(key)

    async def enter_text(self, text: str) -> None:
        if self._text_mode == "sequential" and text.isprintable():
            await self._dispatch("keyboard.type", self._backend.type, text)
        else:
            await self._dispatch("keyboard.insert_text", self._backend.insert_text, text)
