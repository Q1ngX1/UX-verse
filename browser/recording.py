"""Capture browser input and a live pointer overlay while Chromium records the page."""

import json
import math
from bisect import bisect_right
from pathlib import Path
from time import time_ns
from uuid import uuid4

from playwright.async_api import BrowserContext, Frame, Page

from logs import EventSink


POINTER_ATTRIBUTE = "data-uxverse-recording-pointer"
HIDE_RECORDING_POINTER = f"[{POINTER_ATTRIBUTE}] {{ visibility: hidden !important; }}"

_INSTALL = r"""
({binding, token, attribute}) => {
    const publish = globalThis[binding].bind(globalThis);
    const documentId = crypto.randomUUID?.() ?? Math.random().toString(36).slice(2);
    let eventIndex = 0;
    let marker, ring, ringTimer;
    let pointerUpdated = false;

    function showPointer(x, y, pressed = false) {
        if (!document.documentElement) return;
        if (!marker?.isConnected) {
            marker = document.createElement('div');
            marker.setAttribute(attribute, '');
            marker.setAttribute('aria-hidden', 'true');
            marker.style.cssText = 'all:initial;position:fixed;left:0;top:0;width:0;height:0;'
                + 'z-index:2147483647;pointer-events:none!important;';
            const layer = marker.attachShadow({mode:'closed'});
            layer.innerHTML = '<style>:host {pointer-events:none!important}'
                + 'svg {position:absolute;left:-9px;top:-9px;width:37px;height:37px;overflow:visible}'
                + '</style><svg viewBox="-9 -9 37 37" aria-hidden="true">'
                + '<circle r="8" fill="none" stroke="#ffba52" stroke-width="2" opacity="0"/>'
                + '<path d="M0 0 L0 19 L5 14 L9 22 L13 20 L9 12 L16 12 Z"'
                + ' fill="#34d9fd" stroke="#102232" stroke-width="1.5" stroke-linejoin="round"/></svg>';
            ring = layer.querySelector('circle');
            document.documentElement.append(marker);
        }
        marker.style.transform = 'translate(' + x + 'px,' + y + 'px)';
        marker.style.display = 'block';
        if (pressed) {
            ring.setAttribute('opacity', '1');
            clearTimeout(ringTimer);
            ringTimer = setTimeout(() => ring.setAttribute('opacity', '0'), 140);
        }
    }

    // Navigation replaces the overlay DOM, but the browser pointer stays in place.
    publish(token, null).then(position => {
        if (!position) return;
        const restore = () => {
            if (!pointerUpdated) showPointer(position.x, position.y);
        };
        if (document.documentElement) restore();
        else document.addEventListener('DOMContentLoaded', restore, {once:true});
    }).catch(() => {});

    const pointer = [
        'pointermove', 'pointerrawupdate', 'pointerdown', 'pointerup', 'pointercancel',
        'pointerout', 'click', 'dblclick', 'contextmenu', 'wheel'
    ];
    const keyboard = ['keydown', 'keyup'];
    const touch = ['touchstart', 'touchmove', 'touchend', 'touchcancel'];
    const text = ['beforeinput', 'input', 'compositionstart', 'compositionupdate', 'compositionend'];
    const position = event => ({
        x: event.clientX, y: event.clientY, screen_x: event.screenX, screen_y: event.screenY,
        browser_time_ms: performance.timeOrigin + event.timeStamp
    });
    for (const name of [...pointer, ...touch, ...keyboard, ...text]) {
        window.addEventListener(name, event => {
            const target = event.composedPath()[0];
            const payload = {
                type: name, document_id: documentId, event_index: ++eventIndex,
                browser_time_ms: performance.timeOrigin + event.timeStamp, trusted: event.isTrusted,
                frame_url: location.href, target: target?.localName ?? null
            };
            if (pointer.includes(name)) {
                Object.assign(payload, position(event), {
                    pointer_type: event.pointerType ?? 'mouse', pointer_id: event.pointerId ?? null,
                    buttons: event.buttons, button: event.button, pressure: event.pressure ?? null,
                    movement_x: event.movementX, movement_y: event.movementY,
                    alt: event.altKey, ctrl: event.ctrlKey, meta: event.metaKey, shift: event.shiftKey
                });
                const samples = event.getCoalescedEvents?.() ?? [];
                if (samples.length) payload.coalesced = samples.map(position);
                if (name === 'wheel') Object.assign(payload, {
                    delta_x: event.deltaX, delta_y: event.deltaY, delta_z: event.deltaZ, delta_mode: event.deltaMode
                });
                if (event.isTrusted && (name === 'pointermove' || name === 'pointerrawupdate' ||
                                        name === 'pointerdown' || name === 'wheel')) {
                    pointerUpdated = true;
                    showPointer(event.clientX, event.clientY, name === 'pointerdown');
                    payload.pointer_visible = true;
                } else if (event.isTrusted && name === 'pointerout' &&
                           (event.relatedTarget?.localName === 'iframe' || event.clientX < 0 ||
                            event.clientX >= innerWidth || event.clientY < 0 || event.clientY >= innerHeight)) {
                    pointerUpdated = true;
                    if (marker) marker.style.display = 'none';
                    payload.pointer_visible = false;
                }
            } else if (touch.includes(name)) {
                const contact = event.changedTouches[0];
                if (contact) {
                    Object.assign(payload, {x: contact.clientX, y: contact.clientY,
                        screen_x: contact.screenX, screen_y: contact.screenY,
                        pointer_type: 'touch', touch_id: contact.identifier});
                    if (event.isTrusted) {
                        pointerUpdated = true;
                        if (name === 'touchstart' || name === 'touchmove') {
                            showPointer(contact.clientX, contact.clientY, name === 'touchstart');
                            payload.pointer_visible = true;
                        } else {
                            if (marker) marker.style.display = 'none';
                            payload.pointer_visible = false;
                        }
                    }
                }
            } else if (keyboard.includes(name)) {
                Object.assign(payload, {
                    key: event.key, code: event.code, location: event.location, repeat: event.repeat,
                    composing: event.isComposing, alt: event.altKey, ctrl: event.ctrlKey,
                    meta: event.metaKey, shift: event.shiftKey
                });
            } else {
                Object.assign(payload, {
                    data: event.data ?? null, input_type: event.inputType ?? null, composing: event.isComposing ?? null
                });
            }
            publish(token, payload).catch(() => {});
        }, {capture: true, passive: true});
    }
}
"""


def _wall_ms() -> float:
    return time_ns() / 1_000_000


class InputRecording:
    """Collect independently observed events with action and page identifiers."""

    def __init__(self, output: Path, emit: EventSink) -> None:
        self.output = output.resolve()
        self.emit = emit
        self._pages: dict[Page, str] = {}
        self._frames: dict[Frame, str] = {}
        self._pointer_positions: dict[Frame, tuple[float, dict[str, float] | None]] = {}
        self._starts: list[float] = []
        self._actions: list[tuple[dict[str, str], float | None]] = []

    async def install(self, context: BrowserContext) -> None:
        token = uuid4().hex
        binding = f"__uxverse_record_{uuid4().hex}"

        def receive(source, credential, event) -> dict[str, float] | None:
            if credential != token:
                return
            page, frame = source["page"], source["frame"]
            if event is None:
                return self._pointer_positions.get(frame, (0, None))[1]
            if not isinstance(event, dict):
                return
            captured = event.get("browser_time_ms")
            if not isinstance(captured, (int, float)) or not math.isfinite(captured):
                return
            if "pointer_visible" in event and captured >= self._pointer_positions.get(frame, (0, None))[0]:
                position = {"x": event["x"], "y": event["y"]} if event["pointer_visible"] else None
                self._pointer_positions[frame] = captured, position
            page_id = self._pages[page]
            if frame not in self._frames:
                self._frames[frame] = uuid4().hex
            index = bisect_right(self._starts, captured) - 1
            fields = {}
            if index >= 0:
                ids, end = self._actions[index]
                if end is None or captured <= end:
                    fields = ids
            self.emit("input_event", **fields, page_id=page_id, frame_id=self._frames[frame],
                      frame_url=event.pop("frame_url", frame.url), input=event)

        def page_opened(page: Page) -> None:
            page_id = uuid4().hex
            self._pages[page] = page_id
            page.on("framedetached", lambda frame: self._pointer_positions.pop(frame, None))
            self.emit("video_page_opened", page_id=page_id, observed_wall_time_ms=_wall_ms())

        context.on("page", page_opened)
        await context.expose_binding(binding, receive)
        arguments = json.dumps({"binding": binding, "token": token, "attribute": POINTER_ATTRIBUTE})
        await context.add_init_script(script=f"({_INSTALL})({arguments})")
        self.emit("recording_started", clock="browser_epoch_ms", coordinates="frame_client_css_pixels")

    def begin_action(self, ids: dict[str, str]) -> None:
        self._starts.append(_wall_ms())
        self._actions.append((ids, None))

    def end_action(self) -> None:
        ids, _ = self._actions[-1]
        self._actions[-1] = ids, _wall_ms()

    def command(self, ids: dict[str, str], method: str, arguments: tuple, options: dict) -> None:
        self.emit("input_command", **ids, method=method, arguments=arguments, options=options,
                  command_time_ms=_wall_ms())

    async def finish(self) -> None:
        videos = []
        for page, page_id in self._pages.items():
            if page.video is None:
                continue
            path = (await page.video.path()).resolve()
            if path.is_file() and path.stat().st_size:
                videos.append({"page_id": page_id, "path": path.relative_to(self.output).as_posix()})
        status = "complete" if videos and videos[0]["page_id"] == next(iter(self._pages.values())) else "incomplete"
        self.emit("recording_finished", status=status, videos=videos)
        (self.output / "recording.json").write_text(
            json.dumps({"format_version": 1, "status": status, "input_log": "inputs.jsonl",
                        "clock": "browser_epoch_ms", "pointer": "live_page_events", "videos": videos},
                       indent=2) + "\n",
            encoding="utf-8",
        )
        if status == "incomplete":
            raise OSError(f"Recording did not produce a video for the starting page: {self.output}")
