import asyncio
import re
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from contextlib import asynccontextmanager, nullcontext
from hashlib import sha256
from pathlib import Path
from time import monotonic
from typing import NotRequired, TypedDict
from urllib.parse import urlsplit
from uuid import uuid4

from playwright.async_api import (
    CDPSession, ConsoleMessage, Error, Locator, Page, Response, Route, WebSocketRoute, async_playwright,
)
from playwright.async_api import TimeoutError as PlaywrightTimeout
from pydantic import HttpUrl

from logs import EventSink, RunEvents

from .actions import (
    MAX_STEPS, Action, Back, Click, FindText, Hover, KeyText, Navigate, PointerAction,
    PressKey, Scroll, Swipe, Tap, TypeText, Wait,
)
from .input_devices import (
    Device, Point, PointerMode, TextInputMode, VirtualKeyboard, VirtualMouse, VirtualTouchscreen,
    cursory_trajectory, smooth_trajectory,
)
from .recording import HIDE_RECORDING_POINTER, InputRecording
from .viewport import Viewport

ACTION_TIMEOUT = 10
RUN_TIMEOUT = 90
CLICK_NAVIGATION_TIMEOUT_MS = 250


class ActionEffect(TypedDict):
    visual_change: bool
    url_changed: bool
    document_scroll_changed: NotRequired[bool]
    editable_focused: NotRequired[bool]
    document_scroll_y: NotRequired[int]
    visual_cycle: NotRequired[bool]
    clicked_disclosure_open: NotRequired[bool]
    rejected: NotRequired[str]


class ControlHint(TypedDict):
    label: str
    kind: str
    x: int
    y: int
    expanded: NotRequired[bool]


class PageObservation(TypedDict):
    observation_id: str
    url: str
    title: str
    screenshot: str
    viewport: dict[str, int]
    effect: NotRequired[ActionEffect]
    controls: NotRequired[list[ControlHint]]
    visible_text: NotRequired[list[str]]


_IS_EDITABLE = """(point) => {
    const element = point ? document.elementFromPoint(point.x, point.y) : document.activeElement;
    return Boolean(element && !element.disabled && !element.readOnly && (
        element.isContentEditable || element.tagName === 'TEXTAREA' ||
        element.tagName === 'INPUT' && ['text', 'search', 'email', 'url', 'tel', 'password', 'number'].includes(element.type)
    ));
}"""

_VISIBLE_CONTROLS = r"""() => {
    const controls = [];
    for (const element of document.querySelectorAll(
        'a[href], button, summary, input:not([type=hidden]):not([type=password]), textarea, select, [role=button], [role=tab]'
    )) {
        if (element.matches(':disabled, [aria-disabled=true]')) continue;
        if (getComputedStyle(element).visibility !== 'visible') continue;
        const rect = element.getBoundingClientRect();
        const left = Math.max(0, rect.left), right = Math.min(innerWidth, rect.right);
        const top = Math.max(0, rect.top), bottom = Math.min(innerHeight, rect.bottom);
        if (right - left < 4 || bottom - top < 4) continue;
        const x = Math.floor((left + right) / 2), y = Math.floor((top + bottom) / 2);
        if (!element.contains(document.elementFromPoint(x, y))) continue;
        const label = (
            element.getAttribute('aria-label') || element.labels?.[0]?.innerText ||
            element.getAttribute('placeholder') || element.innerText || element.getAttribute('title') || ''
        ).replace(/\s+/g, ' ').trim().slice(0, 100);
        if (!label) continue;
        const role = element.getAttribute('role');
        const kind = role === 'button' || role === 'tab' ? role : element.localName;
        const control = {label, kind, x, y};
        const expanded = element.getAttribute('aria-expanded');
        if (expanded === 'true' || expanded === 'false') {
            control.expanded = expanded === 'true';
        } else if (kind === 'summary' && element.parentElement?.tagName === 'DETAILS') {
            control.expanded = element.parentElement.open;
        }
        controls.push(control);
        if (controls.length === 32) break;
    }
    return controls;
}"""

_VISIBLE_TEXT = r"""() => {
    const root = document.querySelector('main, [role="main"], #body') || document.body;
    const blocks = [];
    let remaining = 1800;
    for (const element of root.querySelectorAll('h1, h2, h3, p, dd, dt, li')) {
        if (element.tagName === 'LI' && element.querySelector('p, ul, ol')) continue;
        const rect = element.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0 || rect.top < 0 || rect.bottom > innerHeight
                || rect.left < 0 || rect.right > innerWidth) continue;
        if (getComputedStyle(element).visibility !== 'visible') continue;
        if (!element.contains(document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2))) continue;
        const text = element.innerText.replace(/\s+/g, ' ').trim();
        if (!text || text.length > remaining) continue;
        blocks.push(text);
        remaining -= text.length;
        if (remaining < 40 || blocks.length === 24) break;
    }
    return blocks;
}"""


class ActionRejected(ValueError):
    """The page stayed usable after rejecting an action."""


def origin(url: str) -> tuple[str, str | None, int | None]:
    parts = urlsplit(url)
    default_port = {"http": 80, "https": 443}.get(parts.scheme)
    port = parts.port
    return parts.scheme, parts.hostname, default_port if port is None else port


class BrowserWorker:
    """Execute one action at a time and record the resulting browser state."""

    def __init__(
        self, page: Page, target: HttpUrl, output: Path, emit: EventSink, *, control_hints: bool = False,
        timeout_seconds: float = RUN_TIMEOUT, text_hints: bool = False, recording: InputRecording | None = None,
        pointer_mode: PointerMode = "direct", text_input: TextInputMode = "insert",
        human_input: bool = False, touch_session: CDPSession | None = None,
    ) -> None:
        self._page = page
        self._origin = origin(str(target))
        self._output = output
        self._emit = emit
        self._control_hints = control_hints
        self._text_hints = text_hints
        self._recording = recording
        self._human_input = human_input
        self._touch = (
            VirtualTouchscreen(page.touchscreen, touch_session, self._dispatch_input) if touch_session else None
        )
        self._step = 0
        self._lock = asyncio.Lock()
        self._deadline = monotonic() + timeout_seconds
        self._last_observation_id: str | None = None
        self._last_visual_hash: bytes | None = None
        self._previous_visual_hash: bytes | None = None
        self._active_action: dict[str, str] = {}
        trajectory = {
            "continuous": smooth_trajectory,
            "cursory": self._cursory_path,
        }.get(pointer_mode)
        self._mouse = VirtualMouse(page.mouse, self._dispatch_input, trajectory, smooth_scroll=human_input)
        self._keyboard = VirtualKeyboard(page.keyboard, self._dispatch_input, text_input)

    def _record(self, event: str, **fields: object) -> None:
        self._emit(event, **self._active_action, **fields)

    async def _route(self, route: Route) -> None:
        request = route.request
        if origin(request.url) == self._origin and request.method in {"GET", "HEAD"}:
            await route.continue_()
            return
        self._record("request_blocked", url=request.url, method=request.method)
        await route.abort()

    async def _close_socket(self, socket: WebSocketRoute) -> None:
        self._record("websocket_blocked", url=socket.url)
        await socket.close()

    def _console_message(self, message: ConsoleMessage) -> None:
        if message.type == "error":
            self._record("console_error", url=self._page.url, message=message.text)

    def _response(self, response: Response) -> None:
        if response.status >= 400:
            self._record("http_error", url=response.url, status=response.status)

    async def _wait_for_navigation(self, before_url: str) -> None:
        try:
            await self._page.wait_for_url(
                lambda url: url != before_url, wait_until="commit", timeout=CLICK_NAVIGATION_TIMEOUT_MS,
            )
        except PlaywrightTimeout:
            pass  # Many interactions update only the current page.

    def _named_links(self, text: str) -> Locator:
        return self._page.get_by_role("link", name=re.compile(re.escape(text), re.IGNORECASE))

    async def has_offscreen_named_link(self, text: str) -> bool:
        links = self._named_links(text)
        if await links.count() != 1:
            return False
        href = await links.get_attribute("href", timeout=1000)
        if not href or not await links.is_visible():
            return False
        url = await links.evaluate("(link) => link.href")
        if origin(url) != self._origin:
            return False
        box = await links.bounding_box(timeout=1000)
        return bool(box and (box["y"] >= self.viewport["height"] or box["y"] + box["height"] <= 0))

    @property
    def viewport(self) -> dict[str, int]:
        size = self._page.viewport_size
        if size is None:
            raise ValueError("The browser worker requires a fixed page viewport.")
        return {"width": size["width"], "height": size["height"]}

    def _cursory_path(self, start: Point, target: Point) -> Iterable[tuple[Point, float]]:
        viewport = self.viewport
        return cursory_trajectory(start, target, viewport=(viewport["width"], viewport["height"]))

    async def _observe(
        self, step: int, *, action: Action, before_url: str, before_scroll: list[int] | None,
    ) -> PageObservation:
        page = self._page
        await page.wait_for_load_state("domcontentloaded")
        image = await page.screenshot(scale="css", style=HIDE_RECORDING_POINTER if self._recording else None)
        title = await page.title()
        url = page.url
        if origin(url) != self._origin:
            raise ValueError(f"Page moved outside the target origin: {url}")
        screenshot = f"screenshots/{step:03}.png"
        path = self._output / screenshot
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(image)
        observation: PageObservation = {
            "observation_id": uuid4().hex, "url": url, "title": title, "screenshot": screenshot,
            "viewport": self.viewport,
        }
        digest = sha256(image).digest()
        if self._last_visual_hash is not None:
            observation["effect"] = {
                "visual_change": digest != self._last_visual_hash,
                "url_changed": url != before_url,
            }
            if before_scroll is not None:
                scroll = await page.evaluate("() => [scrollX, scrollY]")
                observation["effect"]["document_scroll_changed"] = scroll != before_scroll
                observation["effect"]["document_scroll_y"] = round(scroll[1])
                observation["effect"]["editable_focused"] = await page.evaluate(_IS_EDITABLE)
            if digest == self._previous_visual_hash and digest != self._last_visual_hash:
                observation["effect"]["visual_cycle"] = True
            if not self._human_input and isinstance(action, Click) and url == before_url:
                disclosure = await page.evaluate("""({x, y}) => {
                    const control = document.elementFromPoint(x, y)?.closest('summary, [aria-expanded]');
                    const expanded = control?.getAttribute('aria-expanded');
                    if (expanded === 'true' || expanded === 'false') return expanded === 'true';
                    if (control?.tagName === 'SUMMARY' && control.parentElement?.tagName === 'DETAILS') {
                        return control.parentElement.open;
                    }
                    return null;
                }""", {"x": action.x, "y": action.y})
                if disclosure is not None:
                    observation["effect"]["clicked_disclosure_open"] = disclosure
        if self._control_hints:
            observation["controls"] = await page.evaluate(_VISIBLE_CONTROLS)
        if self._text_hints:
            observation["visible_text"] = await page.evaluate(_VISIBLE_TEXT)
        self._previous_visual_hash, self._last_visual_hash = self._last_visual_hash, digest
        return observation

    async def _dispatch_input(self, method: str, dispatch: Callable[..., Awaitable[None]], *arguments, **options) -> None:
        if self._recording:
            self._recording.command(self._active_action, method, arguments, options)
        await dispatch(*arguments, **options)

    async def _perform(self, action: Action) -> None:
        page = self._page
        if self._human_input and (isinstance(action, (Back, FindText))
                                  or isinstance(action, TypeText) and not isinstance(action, KeyText)):
            raise ValueError("This action is unavailable to the human-input runner.")
        viewport = self.viewport
        if isinstance(action, PointerAction) and (action.x >= viewport["width"] or action.y >= viewport["height"]):
            raise ValueError("Pointer coordinates are outside the viewport.")
        if isinstance(action, Swipe) and (action.end_x >= viewport["width"] or action.end_y >= viewport["height"]):
            raise ValueError("Swipe endpoint is outside the viewport.")
        if self._touch and isinstance(action, (Click, Hover, Scroll, PressKey)):
            raise ActionRejected("Use touch gestures in mobile mode.")
        if not self._touch and isinstance(action, (Tap, Swipe)):
            raise ActionRejected("Touch gestures require mobile mode.")
        match action:
            case Navigate(url=url):
                if url.username is not None or origin(str(url)) != self._origin:
                    raise ValueError("Navigation requires a URL on the target origin without credentials.")
                await page.goto(str(url), wait_until="domcontentloaded")
            case Click(x=x, y=y) | Hover(x=x, y=y):
                if isinstance(action, Click):
                    before_url = page.url
                    await self._mouse.click(x, y)
                    await self._wait_for_navigation(before_url)
                else:
                    await self._mouse.move(x, y)
            case Scroll(dx=dx, dy=dy):
                await self._mouse.wheel(dx, dy)
                await page.evaluate("""() => new Promise(resolve => {
                    requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
                })""")
            case Tap(x=x, y=y) if self._touch:
                before_url = page.url
                await self._touch.tap(x, y)
                await self._wait_for_navigation(before_url)
            case Swipe(x=x, y=y, end_x=end_x, end_y=end_y) if self._touch:
                await self._touch.swipe((x, y), (end_x, end_y))
                await page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
            case Back():
                await page.go_back(wait_until="domcontentloaded")
            case TypeText(x=x, y=y, text=text) if self._touch:
                if not await page.evaluate(_IS_EDITABLE, {"x": x, "y": y}):
                    raise ActionRejected("Text entry requires a visible editable field.")
                await self._touch.tap(x, y)
                if not await page.evaluate(_IS_EDITABLE):
                    raise ActionRejected("The field did not receive focus after tapping.")
                await self._keyboard.press("ControlOrMeta+A")
                if self._human_input:
                    await self._keyboard.type_keys(text)
                else:
                    await self._keyboard.enter_text(text)
            case KeyText(x=x, y=y, text=text) if self._human_input:
                await self._mouse.click(x, y)
                await self._keyboard.press("ControlOrMeta+A")
                await self._keyboard.type_keys(text)
            case TypeText(x=x, y=y, text=text):
                if not await page.evaluate(_IS_EDITABLE, {"x": x, "y": y}):
                    raise ActionRejected("Text entry requires an editable field at the supplied coordinates.")
                await self._mouse.prepare_click(x, y)
                if not await page.evaluate(_IS_EDITABLE, {"x": x, "y": y}):
                    raise ActionRejected("The editable target moved before the click. Recheck the visible field.")
                await self._mouse.click(x, y)
                if not await page.evaluate(_IS_EDITABLE):
                    raise ActionRejected("The editable target did not receive focus. Recheck the visible field.")
                await self._keyboard.press("ControlOrMeta+A")
                await self._keyboard.enter_text(text)
            case PressKey(key=key):
                if key == "Enter" and not self._human_input:
                    allowed = await page.evaluate("""() => {
                        const field = document.activeElement;
                        const form = field?.form;
                        return field?.matches('input[type="search"], input[name="q"]') &&
                            form?.method === 'get' && new URL(form.action).origin === location.origin;
                    }""")
                    if not allowed:
                        raise ActionRejected("Enter requires focus in a search input in a same-origin GET form.")
                before_url = page.url
                await self._keyboard.press(key)
                if key == "Enter":
                    await self._wait_for_navigation(before_url)
            case FindText(text=text, links_only=links_only):
                matches = self._named_links(text) if links_only else page.get_by_text(text, exact=False)
                for index in range(min(await matches.count(), 40)):
                    match = matches.nth(index)
                    if await match.is_visible():
                        await match.scroll_into_view_if_needed(timeout=2000)
                        break
                else:
                    raise ActionRejected("No displayed text matched the query on this page.")
            case Wait(ms=ms):
                await asyncio.sleep(ms / 1000)

    async def execute(
        self, action: Action, *, action_id: str | None = None, decision_id: str | None = None,
        recover_rejection: bool = False,
    ) -> PageObservation:
        async with self._lock:
            if self._step >= MAX_STEPS:
                raise ValueError(f"A run is limited to {MAX_STEPS} actions.")
            self._step += 1
            started = monotonic()
            fields = {
                "step": self._step,
                "action": action.model_dump(mode="json"),
                "before_url": self._page.url,
                "before_observation_id": self._last_observation_id,
            }
            self._active_action = {"action_id": action_id or uuid4().hex}
            if decision_id is not None:
                self._active_action["decision_id"] = decision_id
            if self._recording:
                self._recording.begin_action(self._active_action)
            try:
                remaining = self._deadline - started
                if remaining <= 0:
                    raise TimeoutError("The browser run reached its time limit.")
                async with asyncio.timeout(min(ACTION_TIMEOUT, remaining)):
                    if not isinstance(action, Navigate) and origin(self._page.url) != self._origin:
                        raise ValueError("Navigate to the target before interacting with the page.")
                    before_scroll = None
                    if self._last_observation_id is not None and not self._human_input:
                        before_scroll = await self._page.evaluate("() => [scrollX, scrollY]")
                    rejection = None
                    try:
                        await self._perform(action)
                    except ActionRejected as error:
                        if not recover_rejection:
                            raise ValueError(str(error)) from error
                        rejection = str(error)
                    state = await self._observe(
                        self._step, action=action, before_url=fields["before_url"], before_scroll=before_scroll,
                    )
                    if rejection is not None and "effect" in state:
                        state["effect"]["rejected"] = rejection
            except (Error, ValueError, TimeoutError, asyncio.CancelledError) as error:
                self._record(
                    "action", **fields, status="failed", after_url=self._page.url,
                    duration_ms=round((monotonic() - started) * 1000),
                    error={"type": type(error).__name__, "message": str(error)},
                )
                raise
            else:
                self._record(
                    "action", **fields, status="rejected" if rejection is not None else "ok", after_url=state["url"],
                    duration_ms=round((monotonic() - started) * 1000), observation=state,
                )
                self._last_observation_id = state["observation_id"]
                return state
            finally:
                if self._recording:
                    self._recording.end_action()
                self._active_action = {}


@asynccontextmanager
async def browser_worker(
    target: HttpUrl, output: Path, *, headed: bool = False, events: RunEvents | None = None,
    control_hints: bool = False, inspect_final: Callable[[Page], Awaitable[None]] | None = None,
    timeout_seconds: float = RUN_TIMEOUT, text_hints: bool = False, record_input: bool = False,
    pointer_mode: PointerMode = "direct", text_input: TextInputMode = "insert",
    human_input: bool = False, viewport: Viewport = Viewport(), device: Device = "desktop",
) -> AsyncIterator[BrowserWorker]:
    if target.username is not None:
        raise ValueError("The target URL must not contain credentials.")
    if human_input and (control_hints or text_hints or pointer_mode == "direct"):
        raise ValueError("The human-input runner requires continuous pointer motion and screenshot-only observation.")
    output.mkdir(parents=True, exist_ok=False)
    run_events = events if events is not None else RunEvents()
    input_log = run_events.open_log(output / "inputs.jsonl", source="input") if record_input else nullcontext()
    with run_events.open_log(output / "actions.jsonl", source="browser") as emit, input_log as emit_input:
        recording = InputRecording(output, emit_input) if emit_input else None
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=not headed)
            try:
                # Playwright's video encoder requires even frame dimensions.
                video_size = {
                    "width": viewport.width + viewport.width % 2,
                    "height": viewport.height + viewport.height % 2,
                }
                context = await browser.new_context(
                    viewport={"width": viewport.width, "height": viewport.height},
                    is_mobile=device == "mobile", has_touch=device == "mobile",
                    accept_downloads=False, service_workers="block",
                    record_video_dir=output / "videos" if recording else None,
                    record_video_size=video_size if recording else None,
                )
                if recording:
                    await recording.install(context)
                page = await context.new_page()
                touch_session = await context.new_cdp_session(page) if device == "mobile" else None
                worker = BrowserWorker(
                    page, target, output, emit, control_hints=control_hints,
                    timeout_seconds=timeout_seconds, text_hints=text_hints,
                    recording=recording,
                    pointer_mode=pointer_mode, text_input=text_input, human_input=human_input,
                    touch_session=touch_session,
                )
                page.on("console", worker._console_message)
                page.on("pageerror", lambda error: worker._record("page_error", url=page.url, message=str(error)))
                context.on("requestfailed", lambda request: worker._record(
                    "request_failed", url=request.url, method=request.method, error=request.failure,
                ))
                context.on("response", worker._response)
                await context.route("**/*", worker._route)
                await context.route_web_socket("**/*", worker._close_socket)
                await context.tracing.start(screenshots=True, snapshots=True)
                scroll_mode = "smooth" if human_input else "direct"
                if device == "mobile":
                    scroll_mode = "swipe"
                worker._record("run_started", target=str(target), viewport=worker.viewport, device=device,
                               pointer_mode=pointer_mode, scroll_mode=scroll_mode,
                               text_input="keys" if human_input else text_input,
                               human_input=human_input)
                try:
                    yield worker
                finally:
                    try:
                        await context.tracing.stop(path=output / "trace.zip")
                        if inspect_final is not None:
                            await inspect_final(page)
                    finally:
                        await context.close()
                        if recording:
                            await recording.finish()
            finally:
                await browser.close()
