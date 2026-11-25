import asyncio
import json
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import sleep

import httpx

from agent.engine import AgentConfig, run_agent
from agent.model import DECISION, DecisionRequest, ModelReply, ModelUsage, RetryableModelError
from browser.actions import Click
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
        elif self.path == "/disclosure":
            body = '''<!doctype html><title>Disclosure fixture</title>
                <style>body{margin:0;min-height:1600px} summary{height:48px}</style>
                <details><summary>Show answer</summary><p>Answer inside.</p></details>
                <a style="position:absolute;top:1400px" href="/next">Offscreen link</a>'''
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


class BrowserSmokeTest(LocalSite, unittest.TestCase):
    def run_browser(self, directory, actions):
        script = directory / "actions.json"
        script.write_text(json.dumps(actions), encoding="utf-8")
        output = directory / "run"
        process = subprocess.run(
            [sys.executable, "-m", "browser", self.url, "--actions", str(script), "--output", str(output)],
            capture_output=True, text=True, timeout=30,
        )
        return process, output

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
            )
            result = await run_agent(config, TestModel(), output, inspect_final=inspect_final)
            self.assertEqual(result.status, "completed")
            decision = [row for row in self.events(output, "agent.jsonl")
                        if row["event"] == "model_decision" and "action_id" in row]
            events = self.events(output, "inputs.jsonl")
            commands = [row for row in events if row["event"] == "input_command"]
            delivered = [row for row in events if row["event"] == "input_event"]
            self.assertEqual({row["run_id"] for row in events}, {decision[0]["run_id"]})
            self.assertTrue(any(row["method"] == "keyboard.insert_text" and row["arguments"] == ["Fern Creek"]
                                and row["action_id"] == decision[0]["action_id"] for row in commands))
            self.assertTrue(any(row["input"]["type"] == "input" and row["input"]["data"] == "Fern Creek"
                                and row.get("decision_id") == decision[0]["decision_id"] for row in delivered))
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

    async def test_named_offscreen_link_is_located_before_choosing_to_follow_it(self):
        requests = []

        class TestModel:
            async def decide(self, request):
                requests.append(request)
                if request.observation.title == "Next page":
                    return ModelReply('{"type":"stop","outcome":"completed","reason":"Opened the named link."}')
                link = next(control for control in request.observation.controls if control["label"] == "Offscreen link")
                return ModelReply(json.dumps({"type": "act", "reason": "Follow the visible link.",
                                              "action": {"type": "click", "x": link["x"], "y": link["y"]}}))

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            config = AgentConfig(target=self.url + "disclosure", task='Open "Offscreen link".',
                                 max_steps=2, control_hints=True)
            result = await run_agent(config, TestModel(), output)
            self.assertEqual((result.status, result.steps, result.model_calls), ("completed", 2, 2))
            self.assertEqual(requests[0].history[0].action.type, "find")
            self.assertEqual(requests[0].observation.title, "Disclosure fixture")
            self.assertEqual(requests[-1].observation.title, "Next page")
            self.assertTrue(any(event["event"] == "named_link_located" for event in self.events(output, "agent.jsonl")))

    async def test_disclosure_cycle_preserves_reopen_and_intercepts_next_close(self):
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
            self.assertEqual((result.status, result.steps, result.model_calls), ("completed", 4, 6))
            self.assertTrue(calls[3].history[-1].effect["visual_cycle"])
            self.assertIn("disclosure is open", calls[4].retry_feedback)

    async def test_repeated_no_effect_click_gets_a_retry_without_dispatch(self):
        calls = []

        class TestModel:
            async def decide(self, request):
                calls.append(request)
                if request.observation.title == "Next page":
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

    async def test_invalid_text_target_is_observed_and_agent_can_recover(self):
        requests: list[DecisionRequest] = []
        decisions = iter([
            {"type": "act", "action": {"type": "type", "x": 400, "y": 400, "text": "answer"}},
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
            self.assertEqual((result.status, result.steps), ("completed", 2))
            effect = requests[1].history[-1].effect
            self.assertIn("editable field", effect["rejected"])
            self.assertEqual(requests[1].observation.title, "Search fixture")
            self.assertTrue(requests[2].history[-1].effect["editable_focused"])
            self.assertEqual(requests[2].observation.title, "Query: answer")
            actions = [event for event in self.events(output) if event["event"] == "action"]
            self.assertEqual(actions[1]["status"], "rejected")
            self.assertEqual(actions[1]["observation"]["effect"], effect)

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
            if observation["page"]["title"] == "Start page":
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
            self.assertEqual(calls[-1]["history"][0]["url"], self.url + "next")
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
                if request.observation.title == "Next page":
                    response = {"type": "stop", "outcome": "completed", "reason": "Reached the next page.",
                                "answer": "Next page"}
                else:
                    response = {"type": "act", "action": {"type": "click", "x": 20, "y": 20}, "reason": "Open Next."}
                return ModelReply(json.dumps(response), ModelUsage(input_tokens=12, output_tokens=4))

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            config = AgentConfig(
                target=self.url, task="Open the next page.", persona="First-time visitor", max_steps=1,
                control_hints=True, text_hints=True,
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
            self.assertEqual(first.observation.controls[0]["label"], "Next")
            self.assertFalse(last.observation.controls)
            self.assertIn("Next page", last.observation.visible_text)
            self.assertEqual(last.history[0].action, Click(x=20, y=20))
            self.assertEqual(last.history[0].url, self.url + "next")
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
