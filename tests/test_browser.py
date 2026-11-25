import asyncio
import json
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from itertools import pairwise
from math import hypot
from pathlib import Path
from random import Random
from time import perf_counter, sleep
from unittest.mock import patch

import httpx

from agent.engine import MAX_SCROLL_AXIS, REACTION_TIME_MS, AgentConfig, run_agent
from agent.model import DECISION, DecisionRequest, ModelReply, ModelUsage, RetryableModelError
from browser.actions import Click
from browser.input_devices import (
    DESKTOP_KEY_INTERVAL_MS, MAX_WHEEL_SPEED, MOBILE_KEY_INTERVAL_MS, VirtualKeyboard, VirtualMouse, cursory_trajectory,
    plan_typing, smooth_wheel_steps,
)
from browser.touch_motion import phoneos_swipe_steps
from models.decision import DecisionAdapter
from models.responses import ResponsesProvider


class TestSite(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/missing":
            self.send_error(404)
            return

        content_type = "text/html; charset=utf-8"
        if self.path == "/search":
            body = '''<!doctype html><title>Search fixture</title>
                <style>body {margin:0} input {position:absolute;left:20px;top:20px;width:300px;height:50px}
                a {position:absolute;left:375px;top:375px;width:100px;height:60px}</style>
                <form onsubmit="document.title='Unexpected submission';return false">
                <input type="search" value="Old query" oninput="document.title='Query: '+this.value"></form>
                <a href="/next">Unrelated link</a>'''
        elif self.path == "/keyboard-search":
            body = '''<!doctype html><title>Keyboard search</title>
                <style>body {margin:0} input {position:absolute;left:20px;top:20px;width:300px;height:50px}</style>
                <form action="/next" method="get"><input type="search" name="q"></form>'''
        elif self.path == "/next?q=Fern+Creek":
            body = "<!doctype html><title>Keyboard results</title><h1>Fern Creek</h1>"
        elif self.path == "/touch":
            body = """<!doctype html><meta name="viewport" content="width=device-width, initial-scale=1">
                <title>Touch fixture</title>
                <style>body{margin:0;min-height:1800px}
                input,button{display:block;width:180px;height:48px}</style>
                <input aria-label="Query"><button>Confirm</button>
                <script>
                  const button = document.querySelector('button');
                  button.addEventListener('touchstart', event => button.dataset.trusted = event.isTrusted);
                  button.addEventListener('click', () => {
                    document.title = button.dataset.trusted + ': ' + document.querySelector('input').value;
                  });
                </script>"""
        elif self.path == "/disclosure":
            body = '''<!doctype html><title>Disclosure fixture</title>
                <style>body{margin:0;min-height:1600px} summary{height:48px}</style>
                <details><summary>Show answer</summary><p>Answer inside.</p></details>
                <a style="position:absolute;top:1400px" href="/next">Offscreen link</a>'''
        elif self.path == "/scroll-box":
            body = '''<!doctype html><title>Scroll 0,0</title>
                <style>
                    #box { margin: 32px; width: 360px; height: 220px; overflow: auto }
                    #box div { width: 1600px; height: 1800px; background: linear-gradient(120deg, gold, teal) }
                </style>
                <div id="box"><div></div></div>
                <script>
                    const box = document.getElementById('box');
                    window.scrollSamples = [];
                    box.addEventListener('scroll', () => {
                        window.scrollSamples.push([box.scrollLeft, box.scrollTop]);
                        document.title = 'Scroll ' + box.scrollLeft + ',' + box.scrollTop;
                    });
                </script>'''
        elif self.path == "/next":
            body = '<title>Loading next page</title><h1></h1><script defer src="/next.js"></script>'
        elif self.path == "/next.js":
            sleep(0.2)
            content_type = "text/javascript; charset=utf-8"
            body = "document.querySelector('h1').textContent = document.title = 'Next page';"
        else:
            port = self.server.server_port
            body = f"""<!doctype html>
                <title>Start page</title>
                <style>
                  body {{ margin: 0; }}
                  a {{ display: block; width: 200px; height: 80px; background: gold; }}
                  a:hover {{ background: teal; }}
                  section {{ height: 900px; background: red; }}
                  section + section {{ background: blue; }}
                </style>
                <a href="/next">Next</a>
                <img src="/missing" alt="">
                <img src="http://localhost:{port}/blocked" alt="">
                <section></section><section></section>
                <script>
                  console.error('fixture console error');
                  throw new Error('fixture page error');
                </script>
            """
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body.encode())


class LocalSite:
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), TestSite)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def events(self, output, name="actions.jsonl"):
        return [json.loads(line) for line in (output / name).read_text(encoding="utf-8").splitlines()]


class InputTrajectoryTest(unittest.TestCase):
    def test_phoneos_swipes_are_seeded_and_finish_with_distinct_speeds(self):
        start, end = (195, 680), (195, 200)
        flick = phoneos_swipe_steps(start, end, flick=True, viewport=(390, 844), rng=Random(7))
        drag = phoneos_swipe_steps(start, end, flick=False, viewport=(390, 844), rng=Random(7))
        self.assertEqual(flick, phoneos_swipe_steps(start, end, flick=True, viewport=(390, 844), rng=Random(7)))
        self.assertEqual(flick[-1][0], end)
        self.assertEqual(drag[-1][0], end)
        self.assertGreater(abs(flick[-2][0][1] - end[1]), abs(drag[-2][0][1] - end[1]))
        self.assertTrue(all(0 <= x < 390 and 0 <= y < 844 and delay > 0
                            for (x, y), delay in flick + drag))

    def test_cursory_preserves_sample_timing_with_viewport_clipping(self):
        with patch("cursory.generate_trajectory", return_value=(
            [(0, 0), (-4.2, 90.6), (70.6, 120.2), (99, 99)], [0, 8, 25, 40],
        )) as generate:
            steps = list(cursory_trajectory((0, 0), (99, 99), viewport=(100, 100)))
        generate.assert_called_once_with((0, 0), (99, 99), frequency=60)
        self.assertEqual(steps, [((0, 91), 0.008), ((71, 99), 0.017), ((99, 99), 0.015)])

    def test_smooth_wheel_preserves_both_axes_and_eases_to_a_stop(self):
        self.assertEqual(list(smooth_wheel_steps(0, 0)), [])
        self.assertEqual(list(smooth_wheel_steps(-1, 0)), [((-1, 0), 1 / MAX_WHEEL_SPEED)])
        for dx, dy in ((120, -600), (-300, 250), (5000, 0)):
            with self.subTest(dx=dx, dy=dy):
                steps = list(smooth_wheel_steps(dx, dy, rng=Random(1)))
                offsets, pauses = zip(*steps, strict=True)
                self.assertEqual(tuple(map(sum, zip(*offsets, strict=True))), (dx, dy))
                self.assertTrue(all(x * dx >= 0 and y * dy >= 0 for x, y in offsets))
                speeds = [hypot(*offset) / pause for offset, pause in steps]
                self.assertGreater(max(speeds), max(speeds[0], speeds[-1]))
                self.assertLessEqual(max(speeds), MAX_WHEEL_SPEED + 1e-9)
                self.assertGreater(sum(pauses), hypot(dx, dy) / MAX_WHEEL_SPEED)

    def test_long_wheel_scrolls_pause_and_vary_with_the_sampled_pace(self):
        first = list(smooth_wheel_steps(0, 1200, rng=Random(1)))
        second = list(smooth_wheel_steps(0, 1200, rng=Random(2)))
        self.assertTrue(any(delta == (0, 0) and delay >= 0.11 for delta, delay in first))
        self.assertNotEqual(sum(delay for _, delay in first), sum(delay for _, delay in second))

    def test_typing_plan_preserves_key_chords_and_adds_a_word_pause(self):
        cases = (("desktop", DESKTOP_KEY_INTERVAL_MS), ("mobile", MOBILE_KEY_INTERVAL_MS))
        for device, (minimum, maximum) in cases:
            with self.subTest(device=device):
                plan = plan_typing("Ab !", device=device, rng=Random(1))
                self.assertEqual([key for key, _ in plan], ["ControlOrMeta+A", "Shift+KeyA", "b", "Space", "Shift+Digit1"])
                self.assertTrue(REACTION_TIME_MS[0] <= plan[0][1] * 1000 <= REACTION_TIME_MS[1])
                self.assertTrue(all(minimum <= delay * 1000 <= maximum for _, delay in plan[1:-1]))
                self.assertGreaterEqual(plan[-1][1] * 1000, minimum + 40)


class InputPacingTest(unittest.IsolatedAsyncioTestCase):
    async def test_typing_waits_after_a_delayed_browser_acknowledgement(self):
        started, finished = [], []

        class SlowKeyboard:
            async def press(self, key):
                started.append(perf_counter())
                if key == "a":
                    await asyncio.sleep(0.08)
                finished.append(perf_counter())

        async def dispatch(method, action, *args):
            await action(*args)

        keyboard = VirtualKeyboard(SlowKeyboard(), dispatch)
        await keyboard.type_keys([("a", 0), ("b", 0.025)])
        self.assertGreaterEqual(started[1] - finished[0], 0.024)

    async def test_wheel_does_not_catch_up_after_a_slow_dispatch(self):
        started = []

        class SlowMouse:
            async def wheel(self, dx, dy):
                started.append(perf_counter())
                if len(started) == 1:
                    await asyncio.sleep(0.12)

        async def dispatch(method, action, *args):
            await action(*args)

        mouse = VirtualMouse(SlowMouse(), dispatch, smooth_scroll=True)
        with patch("browser.input_devices.smooth_wheel_steps", return_value=[((0, 25), 0.025)] * 3):
            await mouse.wheel(0, 75)
        self.assertGreaterEqual(started[2] - started[1], 0.024)


class BrowserSmokeTest(LocalSite, unittest.TestCase):
    def run_browser(self, directory, actions, *options):
        script = directory / "actions.json"
        script.write_text(json.dumps(actions), encoding="utf-8")
        output = directory / "run"
        process = subprocess.run(
            [sys.executable, "-m", "browser", self.url, "--actions", str(script), "--output", str(output), *options],
            capture_output=True, text=True, timeout=30,
        )
        return process, output

    def test_cursory_mode_records_browser_pointer_path_before_click(self):
        with tempfile.TemporaryDirectory() as directory:
            process, output = self.run_browser(
                Path(directory), [{"type": "hover", "x": 360, "y": 820}, {"type": "click", "x": 100, "y": 40}],
                "--viewport", "390x844", "--pointer-mode", "cursory", "--record-input",
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            events = self.events(output)
            self.assertEqual(events[0]["pointer_mode"], "cursory")
            self.assertEqual(events[0]["viewport"], {"width": 390, "height": 844})
            hover = next(row for row in events if row.get("action", {}).get("type") == "hover")
            click = next(row for row in events if row.get("action", {}).get("type") == "click")
            self.assertEqual(click["after_url"], self.url + "next")
            recorded = [row for row in self.events(output, "inputs.jsonl") if row["event"] == "input_event"]
            hover_moves = [row["input"] for row in recorded if row.get("action_id") == hover["action_id"]
                           and row["input"]["type"] == "pointermove"]
            inputs = [row["input"] for row in recorded if row.get("action_id") == click["action_id"]]
            moves = [event for event in inputs if event["type"] == "pointermove"]
            down = next(event for event in inputs if event["type"] == "pointerdown")
            self.assertEqual((hover_moves[-1]["x"], hover_moves[-1]["y"]), (360, 820))
            self.assertGreater(len({(event["x"], event["y"]) for event in moves}), 2)
            self.assertTrue(all(event["trusted"] and 0 <= event["x"] < 390 and 0 <= event["y"] < 844
                                for event in hover_moves + moves))
            self.assertLess(moves[0]["browser_time_ms"], down["browser_time_ms"])
            self.assertEqual((down["x"], down["y"]), (100, 40))

    def test_sequential_virtual_keyboard_preserves_mixed_text(self):
        with tempfile.TemporaryDirectory() as directory:
            process, output = self.run_browser(
                Path(directory), [{"type": "navigate", "url": self.url + "search"},
                                  {"type": "type", "x": 150, "y": 40, "text": "Ab 溪"}],
                "--text-input", "sequential", "--record-input",
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            actions = [row for row in self.events(output) if row["event"] == "action"]
            self.assertEqual(actions[-1]["observation"]["title"], "Query: Ab 溪")
            events = self.events(output, "inputs.jsonl")
            self.assertTrue(any(row.get("method") == "keyboard.type" and row["arguments"] == ["Ab 溪"]
                                for row in events))
            self.assertTrue(any(row.get("input", {}).get("type") == "keydown"
                                and row["input"]["key"] == "b" for row in events))

    def test_scripted_browsing_records_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            process, output = self.run_browser(Path(directory), [
                {"type": "hover", "x": 20, "y": 20},
                {"type": "click", "x": 20, "y": 20},
                {"type": "back"},
                {"type": "scroll", "dy": 1000},
                {"type": "wait", "ms": 200},
            ])
            self.assertEqual(process.returncode, 0, process.stderr)
            events = self.events(output)
            actions = [event for event in events if event["event"] == "action"]
            self.assertEqual([event["action"]["type"] for event in actions], [
                "navigate", "hover", "click", "back", "scroll", "wait",
            ])
            images = []
            for step, event in enumerate(actions, start=1):
                self.assertEqual(event["status"], "ok")
                self.assertEqual(event["step"], step)
                image = (output / event["observation"]["screenshot"]).read_bytes()
                self.assertEqual(image[:8], b"\x89PNG\r\n\x1a\n")
                self.assertEqual(struct.unpack(">II", image[16:24]), (1280, 720))
                images.append(image)
            self.assertNotEqual(images[0], images[1])
            self.assertEqual(actions[2]["after_url"], self.url + "next")
            self.assertEqual(actions[2]["observation"]["title"], "Next page")
            self.assertEqual(actions[3]["after_url"], self.url)
            self.assertNotEqual(images[3], images[4])
            self.assertTrue({"console_error", "page_error", "http_error", "request_blocked"}
                            <= {event["event"] for event in events})
            with zipfile.ZipFile(output / "trace.zip") as trace:
                self.assertIsNone(trace.testzip())
                self.assertTrue(any(name.endswith(".trace") for name in trace.namelist()))

    def test_failed_action_preserves_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            process, output = self.run_browser(Path(directory), [{"type": "click", "x": 1280, "y": 20}])
            self.assertEqual(process.returncode, 1, process.stderr)
            self.assertIn("outside the viewport", process.stderr)
            actions = [event for event in self.events(output) if event["event"] == "action"]
            self.assertEqual([event["status"] for event in actions], ["ok", "failed"])
            self.assertEqual(actions[-1]["error"]["type"], "ValueError")
            self.assertNotEqual(actions[0]["action_id"], actions[1]["action_id"])
            self.assertEqual(actions[1]["before_observation_id"], actions[0]["observation"]["observation_id"])
            self.assertNotIn("observation", actions[1])
            self.assertTrue((output / "screenshots" / "001.png").is_file())
            self.assertTrue(zipfile.is_zipfile(output / "trace.zip"))

    def test_scripted_viewport_controls_screenshot_size_and_pointer_bounds(self):
        with tempfile.TemporaryDirectory() as directory:
            process, output = self.run_browser(
                Path(directory), [{"type": "click", "x": 390, "y": 20}], "--viewport", "390x844",
            )
            self.assertEqual(process.returncode, 1, process.stderr)
            self.assertIn("outside the viewport", process.stderr)
            events = self.events(output)
            started = next(event for event in events if event["event"] == "run_started")
            initial = next(event["observation"] for event in events if event["event"] == "action")
            self.assertEqual(started["viewport"], {"width": 390, "height": 844})
            self.assertEqual(initial["viewport"], started["viewport"])
            image = (output / initial["screenshot"]).read_bytes()
            self.assertEqual(struct.unpack(">II", image[16:24]), (390, 844))

    def test_coordinate_text_entry_replaces_value_and_does_not_submit(self):
        with tempfile.TemporaryDirectory() as directory:
            query = 'Fern Creek Loop <literal> "溪流"'
            process, output = self.run_browser(Path(directory), [
                {"type": "navigate", "url": self.url + "search"},
                {"type": "type", "x": 150, "y": 40, "text": query},
                {"type": "type", "x": 150, "y": 40, "text": "Replacement query"},
            ])
            self.assertEqual(process.returncode, 0, process.stderr)
            actions = [event for event in self.events(output) if event["event"] == "action"]
            self.assertEqual(actions[-2]["observation"]["title"], "Query: " + query)
            self.assertEqual(actions[-1]["observation"]["title"], "Query: Replacement query")
            self.assertEqual(actions[-1]["after_url"], self.url + "search")
            self.assertEqual(actions[-1]["action"]["text"], "Replacement query")
            self.assertNotEqual(actions[-2]["observation"]["screenshot"], actions[-1]["observation"]["screenshot"])

    def test_text_entry_rejects_noneditable_target_with_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            process, output = self.run_browser(Path(directory), [
                {"type": "type", "x": 400, "y": 400, "text": "Query"},
            ])
            self.assertEqual(process.returncode, 1)
            self.assertIn("editable field", process.stderr)
            last = [event for event in self.events(output) if event["event"] == "action"][-1]
            self.assertEqual(last["status"], "failed")
            self.assertEqual(last["error"]["type"], "ValueError")
            self.assertTrue(zipfile.is_zipfile(output / "trace.zip"))

    def test_enter_is_allowed_only_for_focused_get_search(self):
        with tempfile.TemporaryDirectory() as directory:
            process, output = self.run_browser(Path(directory), [
                {"type": "navigate", "url": self.url + "keyboard-search"},
                {"type": "type", "x": 150, "y": 40, "text": "Fern Creek"},
                {"type": "key", "key": "Enter"},
            ])
            self.assertEqual(process.returncode, 0, process.stderr)
            actions = [event for event in self.events(output) if event["event"] == "action"]
            self.assertEqual(actions[-1]["observation"]["title"], "Keyboard results")
            self.assertTrue(actions[-1]["observation"]["effect"]["url_changed"])

        with tempfile.TemporaryDirectory() as directory:
            process, _ = self.run_browser(Path(directory), [{"type": "key", "key": "Enter"}])
            self.assertEqual(process.returncode, 1)
            self.assertIn("same-origin GET form", process.stderr)

    def test_find_scrolls_to_displayed_text_without_pursuing_links_or_hidden_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            process, output = self.run_browser(Path(directory), [
                {"type": "navigate", "url": self.url + "disclosure"},
                {"type": "find", "text": "Offscreen link"},
            ])
            self.assertEqual(process.returncode, 0, process.stderr)
            actions = [event for event in self.events(output) if event["event"] == "action"]
            self.assertEqual(actions[-1]["after_url"], self.url + "disclosure")
            self.assertTrue(actions[-1]["observation"]["effect"]["document_scroll_changed"])
        with tempfile.TemporaryDirectory() as directory:
            process, _ = self.run_browser(Path(directory), [
                {"type": "navigate", "url": self.url + "disclosure"},
                {"type": "find", "text": "Answer inside"},
            ])
            self.assertEqual(process.returncode, 1)
            self.assertIn("No displayed text matched", process.stderr)


class AgentSmokeTest(LocalSite, unittest.IsolatedAsyncioTestCase):
    def assert_typing_paced(self, events, action_id, text, focus_method, minimum_gap):
        associated = [row for row in events if row.get("action_id") == action_id]
        focus = next(row for row in associated if row.get("method") == focus_method)
        presses = [row for row in associated if row.get("method") == "keyboard.press"]
        self.assertEqual(len(presses), len(text) + 1)
        self.assertEqual(presses[0]["arguments"], ["ControlOrMeta+A"])
        self.assertGreaterEqual(presses[0]["command_time_ms"] - focus["command_time_ms"], REACTION_TIME_MS[0] - 5)
        for previous, current in pairwise(presses):
            self.assertGreaterEqual(current["command_time_ms"] - previous["command_time_ms"], minimum_gap - 5)
        typed = [row["input"] for row in associated if row.get("input", {}).get("type") == "input"]
        self.assertEqual("".join(event["data"] or "" for event in typed), text)
        self.assertTrue(all(event["trusted"] for event in typed))
        for previous, current in pairwise(typed):
            self.assertGreaterEqual(current["browser_time_ms"] - previous["browser_time_ms"], minimum_gap - 15)

    async def test_agent_scroll_delivers_timed_wheel_events_to_pointer_container(self):
        decisions = iter([
            {"type": "act", "action": {"type": "hover", "x": 150, "y": 120}},
            {"type": "act", "action": {"type": "scroll", "dx": 0, "dy": MAX_SCROLL_AXIS + 1}},
            {"type": "act", "action": {"type": "scroll", "dx": 260, "dy": 430}},
            {"type": "act", "action": {"type": "scroll", "dx": -120, "dy": -210}},
            {"type": "stop", "outcome": "completed"},
        ])

        class TestModel:
            async def decide(self, request):
                decision = next(decisions)
                if decision.get("action", {}).get("dy") == -210:
                    await asyncio.sleep(REACTION_TIME_MS[1] / 1000 + 0.05)
                return ModelReply(json.dumps({**decision, "reason": "Scroll inside the box."}))

        async def inspect_final(page):
            self.assertEqual(await page.evaluate("[scrollX, scrollY]"), [0, 0])
            samples = await page.evaluate("window.scrollSamples")
            self.assertGreater(len({y for _, y in samples if 0 < y < 430}), 8)
            self.assertEqual(samples[-1], [140, 220])

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            config = AgentConfig(target=self.url + "scroll-box", task="Scroll within the box.", record_input=True)
            result = await run_agent(config, TestModel(), output, inspect_final=inspect_final)
            self.assertEqual((result.status, result.steps, result.model_calls), ("completed", 3, 5))
            actions = self.events(output)
            self.assertEqual(actions[0]["scroll_mode"], "smooth")
            scrolls = [event for event in actions if event.get("action", {}).get("type") == "scroll"]
            self.assertEqual([event["observation"]["title"] for event in scrolls], ["Scroll 260,430", "Scroll 140,220"])
            inputs = self.events(output, "inputs.jsonl")
            agent_events = self.events(output, "agent.jsonl")
            self.assertEqual(sum(event["event"] == "invalid_decision" for event in agent_events), 1)
            reactions = [event for event in agent_events if event["event"] == "reaction_timing"]
            self.assertEqual(len(reactions), 3)
            self.assertTrue(all(REACTION_TIME_MS[0] <= event["target_ms"] <= REACTION_TIME_MS[1]
                                and event["observation_to_action_ms"] >= event["target_ms"] for event in reactions))
            self.assertGreater(reactions[0]["added_wait_ms"], 100)
            self.assertEqual(reactions[-1]["added_wait_ms"], 0)
            browser_actions = [event for event in actions if event["event"] == "action"]
            for previous, current in pairwise(browser_actions):
                observed_ms = datetime.fromisoformat(previous["timestamp"]).timestamp() * 1000
                first_input = next(event for event in inputs if event.get("action_id") == current["action_id"]
                                   and event["event"] == "input_command")
                self.assertGreaterEqual(first_input["command_time_ms"] - observed_ms, REACTION_TIME_MS[0] - 5)
            for scroll in scrolls:
                associated = [event for event in inputs if event.get("action_id") == scroll["action_id"]]
                commands = [event for event in associated if event["event"] == "input_command"]
                self.assertTrue(all(event["method"] == "mouse.wheel" for event in commands))
                self.assertEqual(tuple(map(sum, zip(*(event["arguments"] for event in commands), strict=True))),
                                 (scroll["action"]["dx"], scroll["action"]["dy"]))
                for previous, current in pairwise(commands):
                    gap = (current["command_time_ms"] - previous["command_time_ms"]) / 1000
                    self.assertLessEqual(hypot(*current["arguments"]), MAX_WHEEL_SPEED * gap * 1.05)
                wheels = [event["input"] for event in associated if event["event"] == "input_event"
                          and event["input"]["type"] == "wheel"]
                self.assertGreater(len(wheels), 8)
                self.assertTrue(all(event["trusted"] and (event["x"], event["y"]) == (150, 120) for event in wheels))
                self.assertGreater(wheels[-1]["browser_time_ms"] - wheels[0]["browser_time_ms"], 100)

    async def test_mobile_exploration_retries_mouse_action_and_uses_trusted_touch(self):
        requests = []
        decisions = iter([
            {"type": "act", "action": {"type": "click", "x": 60, "y": 75}, "reason": "Wrong device action."},
            {"type": "act", "action": {"type": "type", "x": 60, "y": 25, "text": "Trail"}, "reason": "Enter query."},
            {"type": "act", "action": {"type": "tap", "x": 60, "y": 75}, "reason": "Confirm query."},
            {"type": "act", "action": {"type": "swipe", "x": 190, "y": 680, "end_x": 190, "end_y": 200},
             "reason": "Explore farther down."},
            {"type": "stop", "outcome": "completed", "reason": "Budget reached.", "answer": "Tried the form."},
        ])

        class TestModel:
            async def decide(self, request):
                requests.append(request)
                return ModelReply(json.dumps(next(decisions)))

        final = {}

        async def inspect_final(page):
            final["scroll"] = await page.evaluate("scrollY")
            final["title"] = await page.title()

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            config = AgentConfig(
                target=self.url + "touch", mode="explore", device="mobile", max_steps=3,
                viewport={"width": 390, "height": 844}, record_input=True,
                touch_motion="phoneos-drag", touch_seed=7,
            )
            result = await run_agent(config, TestModel(), output, inspect_final=inspect_final)
            self.assertEqual((result.status, result.steps, result.answer), ("completed", 3, "Tried the form."))
            self.assertEqual((requests[0].mode, requests[0].device), ("explore", "mobile"))
            self.assertTrue(requests[1].retry_feedback)
            self.assertEqual(requests[-1].steps_remaining, 0)
            self.assertEqual(final["title"], "true: Trail")
            self.assertGreater(final["scroll"], 0)
            self.assertEqual(self.events(output)[0]["scroll_mode"], "swipe")
            reactions = [row for row in self.events(output, "agent.jsonl") if row["event"] == "reaction_timing"]
            self.assertEqual(len(reactions), 3)
            self.assertTrue(all(row["observation_to_action_ms"] >= REACTION_TIME_MS[0] for row in reactions))
            events = self.events(output, "inputs.jsonl")
            self.assert_typing_paced(events, reactions[0]["action_id"], "Trail", "touchscreen.tap", MOBILE_KEY_INTERVAL_MS[0])
            self.assertEqual(self.events(output)[0]["touch_motion"], "phoneos-drag")
            self.assertTrue(any(row.get("input", {}).get("type") == "touchmove"
                                and row["input"]["trusted"] for row in events))
            self.assertFalse(any(row.get("method", "").startswith("mouse.") for row in events))

    async def test_live_recording_correlates_model_text_keys_and_observed_motion(self):
        actions = iter([
            {"type": "act", "action": {"type": "type", "x": 150, "y": 40, "text": "Fern Creek"}},
            {"type": "act", "action": {"type": "key", "key": "ArrowDown"}},
            {"type": "act", "action": {"type": "key", "key": "Enter"}},
            {"type": "stop", "outcome": "completed"},
        ])

        class TestModel:
            async def decide(self, request):
                return ModelReply(json.dumps({**next(actions), "reason": "Find the search result."}))

        async def inspect_final(page):
            self.assertEqual(await page.title(), "Keyboard results")
            cursor = page.locator("[data-uxverse-recording-pointer]")
            await cursor.wait_for(state="attached", timeout=2000)
            self.assertEqual(await cursor.evaluate("(node) => node.style.transform"), "translate(150px, 40px)")
            self.assertEqual(await cursor.evaluate("(node) => node.style.display"), "block")
            await page.mouse.move(650, 420, steps=16)
            await asyncio.sleep(0.15)

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            config = AgentConfig(
                target=self.url + "keyboard-search", task="Find Fern Creek.", max_steps=3, record_input=True,
                pointer_mode="continuous",
            )
            result = await run_agent(config, TestModel(), output, inspect_final=inspect_final)
            self.assertEqual(result.status, "completed")
            decision = [row for row in self.events(output, "agent.jsonl")
                        if row["event"] == "model_decision" and "action_id" in row]
            events = self.events(output, "inputs.jsonl")
            commands = [row for row in events if row["event"] == "input_command"]
            delivered = [row for row in events if row["event"] == "input_event"]
            self.assertEqual({row["run_id"] for row in events}, {decision[0]["run_id"]})
            self.assertTrue(any(row["method"] == "keyboard.press" and row["arguments"] == ["Shift+KeyF"]
                                and row["action_id"] == decision[0]["action_id"] for row in commands))
            self.assertFalse(any(row["method"] in {"keyboard.type", "keyboard.insert_text"} for row in commands))
            self.assert_typing_paced(events, decision[0]["action_id"], "Fern Creek", "mouse.click",
                                     DESKTOP_KEY_INTERVAL_MS[0])
            approach = [row["input"] for row in delivered if row["input"]["type"] == "pointermove"
                        and row.get("decision_id") == decision[0]["decision_id"]]
            self.assertGreaterEqual(len({row["x"] for row in approach}), 4)
            self.assertEqual((approach[-1]["x"], approach[-1]["y"]), (150, 40))
            self.assertEqual(
                {row["input"]["type"] for row in delivered if row["input"].get("key") == "ArrowDown"
                 and row.get("decision_id") == decision[1]["decision_id"]}, {"keydown", "keyup"},
            )
            self.assertTrue(any(row["input"].get("key") == "Enter"
                                and row.get("decision_id") == decision[2]["decision_id"] for row in delivered))
            motion = [row for row in delivered if row["input"]["type"] == "pointermove"
                      and row["frame_url"].endswith("/next?q=Fern+Creek")]
            self.assertGreaterEqual(len({row["input"]["x"] for row in motion}), 16)
            self.assertEqual((motion[-1]["input"]["x"], motion[-1]["input"]["y"]), (650, 420))
            self.assertTrue(all(row["input"]["trusted"] and "action_id" not in row for row in motion))
            manifest = json.loads((output / "recording.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["videos"][0]["page_id"], motion[-1]["page_id"])
            self.assertGreater((output / manifest["videos"][0]["path"]).stat().st_size, 0)

    async def test_typing_budget_rejects_an_impossible_plan_and_allows_long_actions(self):
        text = 'Fern Creek, route #123!'
        decisions = iter([
            {"type": "act", "action": {"type": "type", "x": 150, "y": 40, "text": "x" * 1000}},
            {"type": "act", "action": {"type": "type", "x": 150, "y": 40, "text": text}},
            {"type": "stop", "outcome": "completed"},
        ])

        class TestModel:
            async def decide(self, request):
                return ModelReply(json.dumps({**next(decisions), "reason": "Enter the whole query."}))

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            config = AgentConfig(target=self.url + "search", task="Type the query.", timeout_seconds=25, record_input=True)
            with patch("browser.worker.ACTION_TIMEOUT", 3):
                result = await run_agent(config, TestModel(), output)
            self.assertEqual((result.status, result.steps), ("completed", 2))
            rejected, accepted = [row for row in self.events(output) if row.get("action", {}).get("type") == "type"]
            self.assertEqual(rejected["status"], "rejected")
            self.assertEqual(rejected["observation"]["title"], "Search fixture")
            self.assertIn("remaining run time", rejected["observation"]["effect"]["rejected"])
            events = self.events(output, "inputs.jsonl")
            self.assertFalse(any(row.get("action_id") == rejected["action_id"] for row in events))
            self.assertEqual((accepted["status"], accepted["observation"]["title"]), ("ok", "Query: " + text))
            self.assertGreater(accepted["duration_ms"], 3000)
            self.assert_typing_paced(events, accepted["action_id"], text, "mouse.click", DESKTOP_KEY_INTERVAL_MS[0])

    async def test_offscreen_link_is_neither_located_nor_dispatched_by_agent(self):
        requests = []

        class TestModel:
            async def decide(self, request):
                requests.append(request)
                if request.retry_feedback:
                    return ModelReply('{"type":"stop","outcome":"gave_up","reason":"Link is offscreen."}')
                return ModelReply('{"type":"act","reason":"Locate it.","action":{"type":"find","text":"Offscreen link"}}')

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            config = AgentConfig(target=self.url + "disclosure", task='Open "Offscreen link".', max_steps=2)
            result = await run_agent(config, TestModel(), output)
            self.assertEqual((result.status, result.steps, result.model_calls), ("gave_up", 0, 2))
            self.assertFalse(requests[0].history)
            self.assertTrue(requests[1].retry_feedback)
            self.assertEqual(set(vars(requests[0].observation)), {"screenshot_png", "width", "height"})
            self.assertEqual([row["action"]["type"] for row in self.events(output)
                              if row["event"] == "action"], ["navigate"])

    async def test_disclosure_cycle_feedback_uses_only_screenshot_changes(self):
        calls = []

        class TestModel:
            async def decide(self, request):
                calls.append(request)
                if request.history and request.history[-1].action.type == "scroll":
                    decision = {"type": "stop", "outcome": "completed", "reason": "Read the open disclosure."}
                elif request.retry_feedback:
                    decision = {"type": "act", "action": {"type": "scroll", "dx": 0, "dy": 150},
                                "reason": "Read below the open disclosure."}
                else:
                    decision = {"type": "act", "action": {"type": "click", "x": 40, "y": 20},
                                "reason": "Click the disclosure."}
                return ModelReply(json.dumps(decision))

        with tempfile.TemporaryDirectory() as directory:
            result = await run_agent(
                AgentConfig(target=self.url + "disclosure", task="Read the answer.", max_steps=4),
                TestModel(), Path(directory) / "run",
            )
            self.assertEqual(result.status, "completed")
            retry = next(call for call in calls if call.retry_feedback)
            self.assertTrue(retry.history[-1].visual_cycle)
            self.assertIn("returned to an earlier screenshot", retry.retry_feedback)

    async def test_repeated_no_effect_click_gets_a_retry_without_dispatch(self):
        calls = []

        class TestModel:
            async def decide(self, request):
                calls.append(request)
                if request.history and request.history[-1].action == Click(x=20, y=20):
                    decision = {"type": "stop", "outcome": "completed", "reason": "Reached the next page."}
                else:
                    point = {"x": 20, "y": 20} if request.retry_feedback else {"x": 400, "y": 400}
                    decision = {"type": "act", "action": {"type": "click", **point}, "reason": "Find the link."}
                return ModelReply(json.dumps(decision))

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            result = await run_agent(AgentConfig(target=self.url, task="Open Next.", max_steps=3), TestModel(), output)
            self.assertEqual((result.status, result.steps, result.model_calls), ("completed", 3, 5))
            self.assertIn("Two clicks", calls[3].retry_feedback)
            rejected = [event for event in self.events(output, "agent.jsonl")
                        if event["event"] == "repeated_action"]
            self.assertEqual(len(rejected), 1)
            self.assertNotIn("action_id", rejected[0])

    async def test_non_ascii_text_is_rejected_before_any_input(self):
        requests: list[DecisionRequest] = []
        decisions = iter([
            {"type": "act", "action": {"type": "type", "x": 400, "y": 400, "text": "溪"}},
            {"type": "act", "action": {"type": "type", "x": 150, "y": 40, "text": "answer"}},
            {"type": "stop", "outcome": "completed"},
        ])

        class TestModel:
            async def decide(self, request):
                requests.append(request)
                return ModelReply(json.dumps({**next(decisions), "reason": "Search for an answer."}))

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            result = await run_agent(
                AgentConfig(target=self.url + "search", task="Search", max_steps=2), TestModel(), output,
            )
            self.assertEqual((result.status, result.steps), ("completed", 1))
            self.assertTrue(requests[1].retry_feedback)
            self.assertFalse(requests[1].history)
            actions = [event for event in self.events(output) if event["event"] == "action"]
            self.assertEqual(len(actions), 2)
            self.assertEqual(actions[1]["observation"]["title"], "Query: answer")

    async def test_agent_explores_through_configured_provider(self):
        calls = []

        def handle(request):
            self.assertEqual(str(request.url), "https://api.openai.com/v1/responses")
            body = json.loads(request.content)
            self.assertEqual(body["model"], "decision-model")
            content = body["input"][0]["content"]
            self.assertTrue(content[1]["image_url"].startswith("data:image/png;base64,iVBOR"))
            observation = json.loads(content[0]["text"])
            calls.append(observation)
            self.assertEqual(set(observation), {"task", "persona", "steps_remaining", "history",
                                                "retry_feedback", "viewport"})
            if not observation["history"]:
                decision = {"type": "act", "reason": "Open the link.", "action": {"type": "click", "x": 20, "y": 20}}
            else:
                decision = {"type": "stop", "reason": "The next page opened.", "outcome": "completed"}
            return httpx.Response(200, json={
                "model": "decision-model-resolved",
                "status": "completed",
                "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(decision)}]}],
            })

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            config = AgentConfig(target=self.url, task="Open the next page.", max_steps=1)
            async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
                model = DecisionAdapter(ResponsesProvider("openai", client, api_key="test-key"), "decision-model")
                result = await run_agent(config, model, output)
            self.assertEqual((result.status, result.steps, result.model_calls), ("completed", 1, 2))
            self.assertEqual(set(calls[-1]["history"][0]), {"action", "visual_change", "visual_cycle"})
            agent_events = self.events(output, "agent.jsonl")
            browser_events = self.events(output)
            timeline = sorted(agent_events + browser_events, key=lambda event: event["seq"])
            self.assertEqual({event["run_id"] for event in timeline}, {timeline[0]["run_id"]})
            self.assertEqual({event["source"] for event in agent_events}, {"agent"})
            self.assertEqual({event["source"] for event in browser_events}, {"browser"})
            self.assertEqual([event["seq"] for event in timeline], list(range(1, len(timeline) + 1)))

            decisions = [event for event in agent_events if event["event"] == "model_decision"]
            self.assertEqual([event["model_id"] for event in decisions], ["decision-model-resolved"] * 2)
            navigate, click = [event for event in browser_events if event["event"] == "action"]
            decision, stop = decisions
            self.assertNotIn("decision_id", navigate)
            self.assertEqual(decision["action_id"], click["action_id"])
            self.assertEqual(decision["decision_id"], click["decision_id"])
            self.assertEqual(decision["observation_id"], click["before_observation_id"])
            self.assertEqual(decision["observation_id"], navigate["observation"]["observation_id"])
            self.assertEqual(stop["observation_id"], click["observation"]["observation_id"])
            self.assertNotIn("action_id", stop)
            self.assertTrue((output / click["observation"]["screenshot"]).is_file())

    async def test_explorer_observes_executes_and_completes_at_step_limit(self):
        requests: list[DecisionRequest] = []

        class TestModel:
            async def decide(self, request):
                requests.append(request)
                if request.history:
                    response = {"type": "stop", "outcome": "completed", "reason": "Reached the next page.",
                                "answer": "Next page"}
                else:
                    response = {"type": "act", "action": {"type": "click", "x": 20, "y": 20}, "reason": "Open Next."}
                return ModelReply(json.dumps(response), ModelUsage(input_tokens=12, output_tokens=4))

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            config = AgentConfig(
                target=self.url, task="Open the next page.", persona="First-time visitor", max_steps=1,
            )
            inspected = []

            async def inspect_final(page):
                self.assertTrue(zipfile.is_zipfile(output / "trace.zip"))
                inspected.append(await page.title())

            result = await run_agent(config, TestModel(), output, inspect_final=inspect_final)
            self.assertEqual((result.status, result.steps, result.model_calls), ("completed", 1, 2))
            self.assertEqual(result.answer, "Next page")
            self.assertEqual(inspected, ["Next page"])
            first, last = requests
            self.assertEqual((first.task, first.persona), (config.task, config.persona))
            self.assertEqual((first.steps_remaining, last.steps_remaining), (1, 0))
            self.assertFalse(first.history)
            self.assertEqual(last.history[0].action, Click(x=20, y=20))
            self.assertTrue(last.history[0].visual_change)
            self.assertEqual((first.observation.width, first.observation.height), (1280, 720))
            self.assertEqual(first.observation.screenshot_png, (output / "screenshots" / "001.png").read_bytes())
            self.assertNotEqual(first.observation.screenshot_png, last.observation.screenshot_png)
            events = self.events(output, "agent.jsonl")
            self.assertEqual(events[1]["observation"]["screenshot"], "screenshots/001.png")
            self.assertEqual(events[2]["usage"]["input_tokens"], 12)
            self.assertEqual(events[-1]["status"], "completed")
            self.assertIn("oneOf", DECISION.json_schema())
            self.assertTrue(zipfile.is_zipfile(output / "trace.zip"))

    async def test_invalid_action_is_retried_and_step_budget_is_enforced(self):
        requests: list[DecisionRequest] = []
        decisions = iter([
            '{"type":"act","action":{"type":"navigate","url":"http://localhost/"},"reason":"Go there."}',
            '{"type":"act","action":{"type":"wait","ms":1},"reason":"Wait for feedback."}',
            '{"type":"act","action":{"type":"wait","ms":1},"reason":"Try another step."}',
        ])

        class TestModel:
            async def decide(self, request):
                requests.append(request)
                return ModelReply(next(decisions))

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            config = AgentConfig(target=self.url, task="Inspect the start page.", max_steps=1)
            result = await run_agent(config, TestModel(), output)
            self.assertEqual((result.status, result.steps, result.model_calls), ("step_limit", 1, 3))
            self.assertIsNone(requests[0].retry_feedback)
            self.assertIsNotNone(requests[1].retry_feedback)
            self.assertIsNone(requests[2].retry_feedback)
            actions = [event["action"]["type"] for event in self.events(output) if event["event"] == "action"]
            self.assertEqual(actions, ["navigate", "wait"])
            agent_events = self.events(output, "agent.jsonl")
            rejected = next(event for event in agent_events if event["event"] == "invalid_decision")
            accepted, over_budget = [event for event in agent_events if event["event"] == "model_decision"]
            self.assertEqual((rejected["attempt"], accepted["attempt"]), (1, 2))
            self.assertEqual(rejected["decision_id"], accepted["decision_id"])
            self.assertEqual(rejected["observation_id"], accepted["observation_id"])
            self.assertNotEqual(accepted["decision_id"], over_budget["decision_id"])
            self.assertNotIn("action_id", rejected)
            self.assertNotIn("action_id", over_budget)

    async def test_run_timeout_preserves_browser_evidence(self):
        class SlowModel:
            async def decide(self, request):
                await asyncio.sleep(60)
                raise AssertionError("The model call should have timed out first.")

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            config = AgentConfig(target=self.url, task="Inspect the start page.", timeout_seconds=2)
            result = await run_agent(config, SlowModel(), output)
            self.assertEqual((result.status, result.steps, result.model_calls), ("timeout", 0, 1))
            self.assertEqual(self.events(output, "agent.jsonl")[-1]["status"], "timeout")
            self.assertTrue((output / "screenshots" / "001.png").is_file())
            self.assertTrue(zipfile.is_zipfile(output / "trace.zip"))

    async def test_failed_model_stops_after_one_retry(self):
        class FailingModel:
            async def decide(self, request):
                if request.retry_feedback is None:
                    raise RetryableModelError("Temporary failure.")
                return ModelReply("invalid JSON")

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            config = AgentConfig(target=self.url, task="Inspect the start page.")
            result = await run_agent(config, FailingModel(), output)
            self.assertEqual((result.status, result.steps, result.model_calls), ("model_error", 0, 2))
            events = self.events(output, "agent.jsonl")
            self.assertTrue({"model_error", "invalid_decision"} <= {event["event"] for event in events})
            actions = [event["action"]["type"] for event in self.events(output) if event["event"] == "action"]
            self.assertEqual(actions, ["navigate"])
