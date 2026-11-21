import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import TextIO, TypedDict
from urllib.parse import urlsplit

from playwright.async_api import ConsoleMessage, Error, Page, Response, Route, WebSocketRoute, async_playwright
from pydantic import HttpUrl

from .actions import MAX_STEPS, Action, Back, Click, Hover, Navigate, Scroll, Wait

VIEWPORT = {"width": 1280, "height": 720}
ACTION_TIMEOUT = 10
RUN_TIMEOUT = 90


class PageObservation(TypedDict):
    url: str
    title: str
    screenshot: str


def origin(url: str) -> tuple[str, str | None, int | None]:
    parts = urlsplit(url)
    default_port = {"http": 80, "https": 443}.get(parts.scheme)
    port = parts.port
    return parts.scheme, parts.hostname, default_port if port is None else port


class BrowserWorker:
    """Execute one action at a time and record the resulting browser state."""

    def __init__(self, page: Page, target: HttpUrl, output: Path, log: TextIO) -> None:
        self._page = page
        self._origin = origin(str(target))
        self._output = output
        self._log = log
        self._step = 0
        self._lock = asyncio.Lock()
        self._deadline = monotonic() + RUN_TIMEOUT

    def _record(self, event: str, **fields: object) -> None:
        row = {"event": event, "timestamp": datetime.now(UTC).isoformat(), **fields}
        self._log.write(json.dumps(row, ensure_ascii=False) + "\n")
        self._log.flush()

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

    async def _observe(self, step: int) -> PageObservation:
        page = self._page
        image = await page.screenshot(scale="css")
        title = await page.title()
        url = page.url
        if origin(url) != self._origin:
            raise ValueError(f"Page moved outside the target origin: {url}")
        screenshot = f"screenshots/{step:03}.png"
        path = self._output / screenshot
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(image)
        return {"url": url, "title": title, "screenshot": screenshot}

    async def _perform(self, action: Action) -> None:
        page = self._page
        match action:
            case Navigate(url=url):
                if url.username is not None or origin(str(url)) != self._origin:
                    raise ValueError("Navigation requires a URL on the target origin without credentials.")
                await page.goto(str(url), wait_until="domcontentloaded")
            case Click(x=x, y=y) | Hover(x=x, y=y):
                if x >= VIEWPORT["width"] or y >= VIEWPORT["height"]:
                    raise ValueError("Pointer coordinates are outside the viewport.")
                if isinstance(action, Click):
                    await page.mouse.click(x, y)
                else:
                    await page.mouse.move(x, y)
            case Scroll(dx=dx, dy=dy):
                await page.mouse.wheel(dx, dy)
                await page.evaluate("""() => new Promise(resolve => {
                    requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
                })""")
            case Back():
                await page.go_back(wait_until="domcontentloaded")
            case Wait(ms=ms):
                await asyncio.sleep(ms / 1000)

    async def execute(self, action: Action) -> PageObservation:
        async with self._lock:
            if self._step >= MAX_STEPS:
                raise ValueError(f"A run is limited to {MAX_STEPS} actions.")
            self._step += 1
            started = monotonic()
            fields = {
                "step": self._step,
                "action": action.model_dump(mode="json"),
                "before_url": self._page.url,
            }
            try:
                remaining = self._deadline - started
                if remaining <= 0:
                    raise TimeoutError("The browser run reached its time limit.")
                async with asyncio.timeout(min(ACTION_TIMEOUT, remaining)):
                    if not isinstance(action, Navigate) and origin(self._page.url) != self._origin:
                        raise ValueError("Navigate to the target before interacting with the page.")
                    await self._perform(action)
                    state = await self._observe(self._step)
            except (Error, ValueError, TimeoutError, asyncio.CancelledError) as error:
                self._record(
                    "action", **fields, status="failed", after_url=self._page.url,
                    duration_ms=round((monotonic() - started) * 1000),
                    error={"type": type(error).__name__, "message": str(error)},
                )
                raise
            self._record(
                "action", **fields, status="ok", after_url=state["url"],
                duration_ms=round((monotonic() - started) * 1000), observation=state,
            )
            return state


@asynccontextmanager
async def browser_worker(target: HttpUrl, output: Path, *, headed: bool = False) -> AsyncIterator[BrowserWorker]:
    if target.username is not None:
        raise ValueError("The target URL must not contain credentials.")
    output.mkdir(parents=True, exist_ok=False)
    with (output / "actions.jsonl").open("x", encoding="utf-8") as log:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=not headed)
            try:
                context = await browser.new_context(
                    viewport=VIEWPORT, accept_downloads=False, service_workers="block",
                )
                page = await context.new_page()
                worker = BrowserWorker(page, target, output, log)
                page.on("console", worker._console_message)
                page.on("pageerror", lambda error: worker._record("page_error", url=page.url, message=str(error)))
                context.on("requestfailed", lambda request: worker._record(
                    "request_failed", url=request.url, method=request.method, error=request.failure,
                ))
                context.on("response", worker._response)
                await context.route("**/*", worker._route)
                await context.route_web_socket("**/*", worker._close_socket)
                await context.tracing.start(screenshots=True, snapshots=True)
                worker._record("run_started", target=str(target), viewport=VIEWPORT)
                try:
                    yield worker
                finally:
                    await context.tracing.stop(path=output / "trace.zip")
                    await context.close()
            finally:
                await browser.close()
