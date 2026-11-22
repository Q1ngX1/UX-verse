"""Loopback-only transport for local multimodal Chat Completions servers."""

from base64 import b64encode
from ipaddress import ip_address
from urllib.parse import urlsplit

import httpx

from .contracts import Completion, ImageInput, ModelError, ModelUsage, RetryableModelError, VideoInput


class LocalProvider:
    def __init__(
        self, client: httpx.AsyncClient, *, base_url: str = "http://127.0.0.1:8081/v1",
        max_output_tokens: int = 512, response_schema: dict[str, object] | None = None,
    ) -> None:
        parts = urlsplit(base_url)
        try:
            loopback = parts.hostname == "localhost" or ip_address(parts.hostname or "").is_loopback
        except ValueError:
            loopback = False
        if (parts.scheme != "http" or not loopback or parts.username is not None
                or parts.password is not None or parts.query or parts.fragment or parts.path.rstrip("/") != "/v1"):
            raise ValueError("The local base URL must be an HTTP loopback address ending in /v1, without credentials.")
        if max_output_tokens < 1:
            raise ValueError("The output token limit must be positive.")
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._client = client
        self._max_output_tokens = max_output_tokens
        self._response_schema = response_schema

    async def complete_json(
        self, model_id: str, *, instructions: str, prompt: str, media: tuple[ImageInput | VideoInput, ...],
    ) -> Completion:
        if not model_id.strip():
            raise ValueError("A model ID is required.")
        if any(not isinstance(item, ImageInput) for item in media):
            raise ModelError("The local provider accepts images only; use timestamped frames for video analysis.")
        content = [{"type": "text", "text": prompt}]
        for item in media:
            data = b64encode(item.data).decode("ascii")
            content.append({"type": "image_url", "image_url": {"url": f"data:{item.mime_type};base64,{data}"}})
        payload = {
            "model": model_id.strip(), "stream": False, "temperature": 0.1,
            "max_tokens": self._max_output_tokens,
            "messages": [{"role": "system", "content": instructions}, {"role": "user", "content": content}],
            "response_format": {"type": "json_object"},
        }
        if self._response_schema is not None:
            payload["response_format"] = {"type": "json_schema", "json_schema": {
                "name": "ux_verse_decision", "strict": True, "schema": self._response_schema,
            }}
        try:
            response = await self._client.post(self._url, json=payload, follow_redirects=False)
        except httpx.TransportError as error:
            raise RetryableModelError(f"Local model transport failed ({type(error).__name__}).") from None
        status = response.status_code
        if status in {408, 429} or 500 <= status < 600:
            raise RetryableModelError(f"Local model returned HTTP {status}.", http_status=status)
        if not response.is_success:
            raise ModelError(f"Local model returned HTTP {status}.", http_status=status)
        try:
            body = response.json()
            choice = body["choices"][0]
            if choice.get("finish_reason") == "length":
                raise ModelError("The local model reached its output token limit.")
            if body.get("error") or choice.get("finish_reason") != "stop":
                raise ModelError("The local model did not complete the request.")
            text = choice["message"]["content"]
            if not isinstance(text, str) or not text.strip():
                raise ModelError("The local model returned no output text.")
            usage = body.get("usage")
            metrics = ModelUsage(usage.get("prompt_tokens"), usage.get("completion_tokens")) if usage else None
            resolved = body.get("model") or model_id
        except (ValueError, AttributeError, KeyError, TypeError, IndexError):
            raise ModelError("The local model returned an invalid response envelope.") from None
        return Completion(text, resolved, metrics)
