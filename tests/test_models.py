import json
import unittest
from unittest.mock import patch

import httpx

from agent.model import DECISION, DecisionRequest, HistoryEntry, Observation
from browser.actions import Click
from models.contracts import ImageInput, ModelError, ModelUsage, RetryableModelError, VideoInput
from models.decision import DecisionAdapter, FlatDecision
from models.responses import ResponsesProvider
from models.temporal import TemporalAdapter, TimedFrame


def completed(value, model_id="resolved-model"):
    return httpx.Response(200, json={
        "status": "completed",
        "model": model_id,
        "output": [
            {"type": "reasoning", "summary": []},
            {"type": "message", "role": "assistant", "content": [
                {"type": "output_text", "text": json.dumps(value)},
            ]},
        ],
        "usage": {"input_tokens": 30, "output_tokens": 10, "cost": 0.01},
    })


class ModelIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_structured_decision_preserves_agent_action_contract(self):
        def handle(request):
            payload = json.loads(request.content)
            self.assertEqual(payload["text"]["format"]["type"], "json_schema")
            self.assertEqual(payload["provider"], {"require_parameters": True})
            prompt = json.loads(payload["input"][0]["content"][0]["text"])
            self.assertEqual(prompt["history"][0]["action"], {"type": "click", "x": 1000, "y": 1000})
            return completed({
                "operation": "click", "x": 723, "y": 53, "dx": 0, "dy": 0, "ms": 0,
                "reason": "Open Routes.", "text": "",
            })

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            provider = ResponsesProvider(
                "openrouter", client, api_key="test-key", response_schema=FlatDecision.model_json_schema(),
            )
            adapter = DecisionAdapter(provider, "google/gemini-2.5-flash-lite", flat_output=True)
            observation = Observation(b"PNG", 1280, 720)
            history = (HistoryEntry(Click(x=1279, y=719), visual_change=True),)
            request = DecisionRequest("Open Routes.", None, observation, history, 6)
            reply = await adapter.decide(request)
        decision = DECISION.validate_json(reply.decision_json)
        self.assertEqual(decision.model_dump()["action"], {"type": "click", "x": 925, "y": 38})

    async def test_timestamped_frames_go_to_both_providers_in_order(self):
        frames = (TimedFrame(0, ImageInput(b"before")), TimedFrame(250, ImageInput(b"after")))

        for name, endpoint in (
            ("openai", "https://api.openai.com/v1/responses"),
            ("openrouter", "https://openrouter.ai/api/v1/responses"),
        ):
            with self.subTest(provider=name):
                def handle(request):
                    self.assertEqual(str(request.url), endpoint)
                    self.assertEqual(request.headers["Authorization"], "Bearer test-key")
                    payload = json.loads(request.content)
                    self.assertEqual(payload["model"], "timeline-model")
                    self.assertEqual(payload["max_output_tokens"], 256)
                    self.assertEqual(payload["text"]["format"], {"type": "json_object"})
                    content = payload["input"][0]["content"]
                    self.assertEqual(json.loads(content[0]["text"])["timestamps_ms"], [0, 250])
                    self.assertEqual([item["image_url"] for item in content[1:]], [
                        "data:image/png;base64,YmVmb3Jl", "data:image/png;base64,YWZ0ZXI=",
                    ])
                    if name == "openai":
                        self.assertIs(payload["store"], False)
                    return completed({"summary": "Panel opened.", "changes": [
                        {"timestamp_ms": 250, "description": "A panel is visible."},
                    ]})

                async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
                    with patch.dict("os.environ", {f"{name.upper()}_API_KEY": "test-key"}):
                        adapter = TemporalAdapter(ResponsesProvider(name, client, max_output_tokens=256), "timeline-model")
                    reply = await adapter.analyze("Check for feedback after clicking.", frames)
                self.assertEqual(reply.model_id, "resolved-model")
                self.assertEqual(reply.usage, ModelUsage(30, 10, 0.01))
                self.assertEqual(reply.analysis.changes[0].timestamp_ms, 250)

    async def test_native_video_uses_the_video_content_part(self):
        requests = []

        def handle(request):
            requests.append(request)
            self.assertEqual(str(request.url), "https://openrouter.ai/api/v1/responses")
            content = json.loads(request.content)["input"][0]["content"]
            self.assertEqual(content[1], {"type": "input_video", "video_url": "data:video/webm;base64,Y2xpcA=="})
            return completed({"summary": "A dialog opened.", "changes": [
                {"timestamp_ms": 680, "description": "The dialog fades in."},
            ]})

        clip = VideoInput(b"clip", "video/webm")
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            adapter = TemporalAdapter(ResponsesProvider("openrouter", client, api_key="test-key"), "video-model")
            reply = await adapter.analyze("Describe the transition.", clip)
            self.assertEqual(reply.analysis.changes[0].timestamp_ms, 680)
            adapter = TemporalAdapter(ResponsesProvider("openai", client, api_key="test-key"), "vision-model")
            with self.assertRaisesRegex(ModelError, "timestamped image frames"):
                await adapter.analyze("Describe the transition.", clip)
        self.assertEqual(len(requests), 1)

    async def test_frame_analysis_rejects_invalid_input_or_invented_frame_times(self):
        request_count = 0

        def handle(request):
            nonlocal request_count
            request_count += 1
            return completed({"summary": "Unsupported claim.", "changes": [
                {"timestamp_ms": 100, "description": "A menu appeared."},
            ]})

        before = TimedFrame(0, ImageInput(b"before"))
        after = TimedFrame(250, ImageInput(b"after"))
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            adapter = TemporalAdapter(ResponsesProvider("openai", client, api_key="test-key"), "vision-model")
            with self.assertRaisesRegex(ValueError, "strictly increasing"):
                await adapter.analyze("Check for a menu.", (after, before))
            with self.assertRaisesRegex(ModelError, "outside the supplied frames"):
                await adapter.analyze("Check for a menu.", (before, after))
        self.assertEqual(request_count, 1)

    async def test_provider_errors_keep_retryable_failures_distinct(self):
        def disconnect(request):
            raise httpx.ReadTimeout("test timeout", request=request)

        for handler, error_type in (
            (lambda request: httpx.Response(429), RetryableModelError),
            (lambda request: httpx.Response(503), RetryableModelError),
            (disconnect, RetryableModelError),
            (lambda request: httpx.Response(401, text="sensitive body"), ModelError),
            (lambda request: httpx.Response(200, json={"status": "incomplete"}), ModelError),
            (lambda request: httpx.Response(200, json={"status": "completed", "output": []}), ModelError),
        ):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                provider = ResponsesProvider("openai", client, api_key="test-key")
                with self.assertRaises(error_type) as failure:
                    await provider.complete_json("test-model", instructions="Return JSON.", prompt="Task", media=())
                self.assertIs(type(failure.exception), error_type)
                self.assertNotIn("sensitive body", str(failure.exception))
                self.assertNotIn("test-key", str(failure.exception))
