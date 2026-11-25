"""Page-scoped input devices for browser actions."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from itertools import pairwise
from math import ceil, hypot
from time import perf_counter
from typing import Literal

from playwright.async_api import Keyboard, Mouse

ContinuousPointerMode = Literal["continuous", "cursory"]
PointerMode = Literal["direct", ContinuousPointerMode]
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


def cursory_trajectory(start: Point, target: Point, *, viewport: Point) -> Iterable[tuple[Point, float]]:
    """Adapt a recorded-motion-based path to viewport pixels and delays in seconds."""
    from cursory import generate_trajectory

    width, height = viewport
    points, timestamps = generate_trajectory(start, target, frequency=60)
    for (x, y), (previous, current) in zip(points[1:], pairwise(timestamps), strict=True):
        point = (min(width - 1, max(0, round(x))), min(height - 1, max(0, round(y))))
        yield point, (current - previous) / 1000


def smooth_wheel_steps(dx: int, dy: int) -> Iterable[tuple[Point, float]]:
    """Yield wheel deltas with acceleration, deceleration, and exact cumulative distance."""
    distance = max(abs(dx), abs(dy))
    if distance <= 1:
        if distance:
            yield (dx, dy), 0
        return

    duration = 0.12 + min(distance, 1080) / 2000
    count = ceil(duration * 60)
    previous_x = previous_y = 0
    for step in range(1, count + 1):
        t = step / count
        fraction = t * t * (3 - 2 * t)
        x, y = (dx, dy) if step == count else (round(dx * fraction), round(dy * fraction))
        yield (x - previous_x, y - previous_y), duration / count
        previous_x, previous_y = x, y


async def _pace(steps: Iterable[tuple[Point, float]]) -> AsyncIterator[Point]:
    deadline = None
    for point, delay in steps:
        # Browser dispatch time should not accumulate as extra delay at every sample.
        deadline = (perf_counter() if deadline is None else deadline) + delay
        await asyncio.sleep(max(0, deadline - perf_counter()))
        yield point


class VirtualMouse:
    def __init__(
        self, backend: Mouse, dispatch: Dispatch, trajectory: Trajectory | None = None, *, smooth_scroll: bool = False,
    ) -> None:
        self._backend = backend
        self._dispatch = dispatch
        self._trajectory = trajectory
        self._smooth_scroll = smooth_scroll
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
            async for point in _pace(self._trajectory(self.position, target)):
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
        if not self._smooth_scroll:
            await self._dispatch("mouse.wheel", self._backend.wheel, dx, dy)
            return
        async for (step_x, step_y) in _pace(smooth_wheel_steps(dx, dy)):
            if step_x or step_y:
                await self._dispatch("mouse.wheel", self._backend.wheel, step_x, step_y)


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
