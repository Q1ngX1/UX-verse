import json
import unittest

import httpx

from agent.model import DECISION, DecisionRequest, Observation
from models.contracts import ImageInput, ModelError, ModelUsage, RetryableModelError, VideoInput
from models.decision import DecisionAdapter, FlatDecision
from models.local import LocalProvider


class LocalProviderTest(unittest.IsolatedAsyncioTestCase):
    def test_named_scroll_direction_controls_delta_sign(self):
        for operation, expected in (("scroll_down", 300), ("scroll_up", -300)):
            reply = FlatDecision(reason="Scroll to read the page.", operation=operation,
                                 x=0, y=0, dx=0, dy=-300, ms=0, text="")
            decision = DECISION.validate_json(reply.decision_json(1280, 720))
            self.assertEqual(decision.action.model_dump(), {"type": "scroll", "dx": 0, "dy": expected})

    async def test_text_decision_preserves_literal_query_and_normalizes_target(self):
        query = 'Fern Creek Loop "溪流"'
        value = {"operation":"type", "reason":"Search the directory.", "x":500, "y":500,
                 "dx":0, "dy":0, "ms":0, "text":query}
        def handle(request):
            schema = json.loads(request.content)["response_format"]["json_schema"]["schema"]
            self.assertIn("type", schema["properties"]["operation"]["enum"])
            self.assertEqual(set(schema["required"]), set(schema["properties"]))
            self.assertEqual(next(iter(schema["properties"])), "reason")
            return httpx.Response(200, json={"choices":[{"finish_reason":"stop", "message":{"content":json.dumps(value)}}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            adapter = DecisionAdapter(LocalProvider(client, response_schema=FlatDecision.model_json_schema()), "local", flat_output=True)
            reply = await adapter.decide(DecisionRequest("Search for a route.", None, Observation("http://localhost/", "Routes", b"PNG",1280,720), (), 4))
        self.assertEqual(DECISION.validate_json(reply.decision_json).action.model_dump(), {
            "type":"type", "text":query, "x":640, "y":360,
        })

    async def test_local_screenshot_decision_uses_chat_schema_without_cloud_credentials(self):
        def handle(request):
            self.assertEqual(str(request.url), "http://127.0.0.1:8081/v1/chat/completions")
            self.assertNotIn("authorization", request.headers)
            payload = json.loads(request.content)
            self.assertEqual(payload["response_format"]["json_schema"]["schema"], FlatDecision.model_json_schema())
            self.assertEqual(payload["messages"][1]["content"][1], {
                "type": "image_url", "image_url": {"url": "data:image/png;base64,UE5H"},
            })
            self.assertEqual(payload["max_tokens"], 512)
            self.assertIn("coordinates of the visible search input", payload["messages"][0]["content"])
            return httpx.Response(200, json={"model": "qwen3-vl-8b-local", "choices": [{
                "finish_reason": "stop", "message": {"content": json.dumps({
                    "operation": "click", "reason": "Open the route directory.",
                    "x": 500, "y": 500, "dx": 0, "dy": 0, "ms": 0, "text": "",
                })},
            }], "usage": {"prompt_tokens": 1400, "completion_tokens": 60}})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            provider = LocalProvider(client, response_schema=FlatDecision.model_json_schema())
            adapter = DecisionAdapter(provider, "qwen3-vl-8b-local", flat_output=True)
            reply = await adapter.decide(DecisionRequest(
                "Open the route directory.", None, Observation("http://localhost/", "Waymark", b"PNG", 1280, 720), (), 6,
            ))
        self.assertEqual(DECISION.validate_json(reply.decision_json).action.model_dump(), {"type": "click", "x": 640, "y": 360})
        self.assertEqual(reply.usage, ModelUsage(1400, 60))

    async def test_local_endpoint_requires_loopback_and_rejects_native_video(self):
        async with httpx.AsyncClient() as client:
            for url in ("https://example.com/v1", "http://192.168.1.2/v1", "http://user:pass@localhost/v1", "http://localhost/v1?key=x"):
                with self.subTest(url=url), self.assertRaises(ValueError):
                    LocalProvider(client, base_url=url)
            with self.assertRaisesRegex(ModelError, "images only"):
                await LocalProvider(client).complete_json("model", instructions="", prompt="", media=(VideoInput(b"video"),))

    async def test_local_errors_distinguish_retryable_truncated_and_malformed_responses(self):
        cases = [
            (httpx.Response(503), RetryableModelError),
            (httpx.Response(400, text="private input"), ModelError),
            (httpx.Response(302, headers={"Location": "https://example.com"}), ModelError),
            (httpx.Response(200, json={"choices": []}), ModelError),
            (httpx.Response(200, json={"choices": [{"finish_reason": "length"}]}), ModelError),
        ]
        for response, kind in cases:
            with self.subTest(status=response.status_code):
                async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: response)) as client:
                    with self.assertRaises(kind) as failure:
                        await LocalProvider(client).complete_json("model", instructions="", prompt="", media=(ImageInput(b"PNG"),))
                    self.assertNotIn("private input", str(failure.exception))
