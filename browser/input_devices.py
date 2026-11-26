"""Page-scoped input devices for browser actions."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from itertools import pairwise
from math import ceil, hypot
from random import Random
from time import perf_counter
from typing import Literal

from playwright.async_api import CDPSession, Keyboard, Mouse, Touchscreen

from .touch_motion import TouchMotion, phoneos_swipe_steps

Device = Literal["desktop", "mobile"]
ContinuousPointerMode = Literal["continuous", "cursory"]
PointerMode = Literal["direct", ContinuousPointerMode]
TextInputMode = Literal["insert", "sequential"]
Dispatch = Callable[..., Awaitable[None]]
Point = tuple[int, int]
Trajectory = Callable[[Point, Point], Iterable[tuple[Point, float]]]
TypingPlan = list[tuple[str, float]]
REACTION_TIME_MS = (450, 700)
DESKTOP_KEY_INTERVAL_MS = (160, 250)
MOBILE_KEY_INTERVAL_MS = (195, 275)
MAX_WHEEL_SPEED = 1000  # CSS pixels per second, measured across both axes.
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


def smooth_wheel_steps(dx: int, dy: int, *, rng: Random | None = None) -> Iterable[tuple[Point, float]]:
    """Yield paced wheel deltas that add up to the requested distance."""
    distance = hypot(dx, dy)
    if distance <= 1:
        if distance:
            yield (dx, dy), distance / MAX_WHEEL_SPEED
        return

    rng = rng or Random()
    strokes = ceil(distance / rng.uniform(650, 850))
    previous_x = previous_y = 0
    for stroke in range(strokes):
        if stroke:
            yield (0, 0), rng.uniform(0.11, 0.20)
        duration = 0.14 + (distance / strokes) / rng.uniform(540, 720)
        count = ceil(duration * 40)
        interval = duration / count
        skew = rng.uniform(0.15, 0.50)
        for step in range(1, count + 1):
            progress = step / count
            # Bring the speed peak forward so the stroke spends longer slowing down.
            t = progress + skew * progress * (1 - progress)
            fraction = (stroke + t * t * (3 - 2 * t)) / strokes
            x, y = round(dx * fraction), round(dy * fraction)
            delta_x, delta_y = x - previous_x, y - previous_y
            yield (delta_x, delta_y), max(interval, hypot(delta_x, delta_y) / MAX_WHEEL_SPEED)
            previous_x, previous_y = x, y


async def _wait_until(deadline: float) -> None:
    while (remaining := deadline - perf_counter()) > 0:
        await asyncio.sleep(remaining)


async def _pace(steps: Iterable[tuple[Point, float]], *, catch_up: bool = True) -> AsyncIterator[Point]:
    deadline = None
    for point, delay in steps:
        deadline = (perf_counter() if deadline is None else deadline) + delay
        if catch_up:
            await asyncio.sleep(max(0, deadline - perf_counter()))
        else:
            await _wait_until(deadline)
            # A delayed wheel tick must not compress the interval before the next one.
            deadline = perf_counter()
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

    async def move(self, x: int, y: int, *, trajectory: Trajectory | None = None) -> None:
        target = (x, y)
        path = trajectory or self._trajectory
        if path is None:
            await self._move(target)
            return
        if target != self.position:
            async for point in _pace(path(self.position, target)):
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
        async for step_x, step_y in _pace(smooth_wheel_steps(dx, dy), catch_up=False):
            if step_x or step_y:
                await self._dispatch("mouse.wheel", self._backend.wheel, step_x, step_y)


class VirtualTouchscreen:
    def __init__(
        self, backend: Touchscreen, session: CDPSession, dispatch: Dispatch, *,
        motion: TouchMotion = "linear", seed: int = 0,
    ) -> None:
        self._backend = backend
        self._session = session
        self._dispatch = dispatch
        self._motion = motion
        self._rng = Random(seed)

    async def tap(self, x: int, y: int) -> None:
        await self._dispatch("touchscreen.tap", self._backend.tap, x, y)

    async def _touch(self, event: str, points: list[dict[str, int]]) -> None:
        await self._dispatch("Input.dispatchTouchEvent", self._session.send, "Input.dispatchTouchEvent",
                             {"type": event, "touchPoints": points})

    async def swipe(self, start: Point, end: Point, *, viewport: Point) -> None:
        steps = (smooth_trajectory(start, end) if self._motion == "linear" else
                 phoneos_swipe_steps(start, end, flick=self._motion == "phoneos-flick",
                                     viewport=viewport, rng=self._rng))
        await self._touch("touchStart", [{"x": start[0], "y": start[1]}])
        try:
            async for x, y in _pace(steps):
                await self._touch("touchMove", [{"x": x, "y": y}])
        finally:
            await self._touch("touchEnd", [])


def plan_typing(text: str, *, device: Device, rng: Random | None = None) -> TypingPlan:
    """Plan a pause after focusing, then select the field contents and type every character."""
    if not text.isascii() or not text.isprintable():
        raise ValueError("Keyboard-only text must be printable ASCII.")
    rng = rng or Random()
    interval = MOBILE_KEY_INTERVAL_MS if device == "mobile" else DESKTOP_KEY_INTERVAL_MS
    steps = [("ControlOrMeta+A", rng.randint(*REACTION_TIME_MS) / 1000)]
    previous = ""
    for character in text:
        if character in _SHIFTED_KEYS:
            key = f"Shift+{_SHIFTED_KEYS[character]}"
        elif character.isupper():
            key = f"Shift+Key{character}"
        else:
            key = "Space" if character == " " else character
        delay = rng.randint(*interval)
        if previous == " " and character != " ":
            delay += rng.randint(40, 90)
        steps.append((key, delay / 1000))
        previous = character
    return steps


class VirtualKeyboard:
    def __init__(self, backend: Keyboard, dispatch: Dispatch, text_mode: TextInputMode = "insert") -> None:
        self._backend = backend
        self._dispatch = dispatch
        self._text_mode = text_mode

    async def press(self, key: str) -> None:
        await self._dispatch("keyboard.press", self._backend.press, key)

    async def type_keys(self, steps: TypingPlan) -> None:
        for key, delay in steps:
            # Start the next interval after Playwright has finished the preceding key press.
            await _wait_until(perf_counter() + delay)
            await self.press(key)

    async def enter_text(self, text: str) -> None:
        if self._text_mode == "sequential" and text.isprintable():
            await self._dispatch("keyboard.type", self._backend.type, text)
        else:
            await self._dispatch("keyboard.insert_text", self._backend.insert_text, text)
