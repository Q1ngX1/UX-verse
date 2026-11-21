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

        if self.path == "/next":
            body = "<title>Next page</title><h1>Next page</h1>"
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
        self.send_header("Content-Type", "text/html; charset=utf-8")
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
            self.assertTrue((output / "screenshots" / "001.png").is_file())
            self.assertTrue(zipfile.is_zipfile(output / "trace.zip"))


class AgentSmokeTest(LocalSite, unittest.IsolatedAsyncioTestCase):
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
            decisions = [event for event in self.events(output, "agent.jsonl") if event["event"] == "model_decision"]
            self.assertEqual([event["model_id"] for event in decisions], ["decision-model-resolved"] * 2)

    async def test_explorer_observes_executes_and_completes_at_step_limit(self):
        requests: list[DecisionRequest] = []

        class TestModel:
            async def decide(self, request):
                requests.append(request)
                if request.observation.title == "Next page":
                    response = {"type": "stop", "outcome": "completed", "reason": "Reached the next page."}
                else:
                    response = {"type": "act", "action": {"type": "click", "x": 20, "y": 20}, "reason": "Open Next."}
                return ModelReply(json.dumps(response), ModelUsage(input_tokens=12, output_tokens=4))

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            config = AgentConfig(target=self.url, task="Open the next page.", persona="First-time visitor", max_steps=1)
            result = await run_agent(config, TestModel(), output)
            self.assertEqual((result.status, result.steps, result.model_calls), ("completed", 1, 2))
            first, last = requests
            self.assertEqual((first.task, first.persona), (config.task, config.persona))
            self.assertEqual((first.steps_remaining, last.steps_remaining), (1, 0))
            self.assertFalse(first.history)
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
            self.assertIn("invalid_decision", {event["event"] for event in self.events(output, "agent.jsonl")})

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
