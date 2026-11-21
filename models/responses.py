import os
from base64 import b64encode
from typing import Literal

import httpx

from .contracts import Completion, ImageInput, ModelError, ModelUsage, RetryableModelError, VideoInput

Provider = Literal["openai", "openrouter"]
_ENDPOINTS = {
    "openai": ("https://api.openai.com/v1/responses", "OPENAI_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1/responses", "OPENROUTER_API_KEY"),
}


def _media_part(media: ImageInput | VideoInput) -> dict[str, str]:
    data_url = f"data:{media.mime_type};base64,{b64encode(media.data).decode('ascii')}"
    if isinstance(media, ImageInput):
        return {"type": "input_image", "image_url": data_url, "detail": "auto"}
    return {"type": "input_video", "video_url": data_url}


class ResponsesProvider:
    """A shared Responses API transport with a caller-owned async HTTP client."""

    def __init__(self, provider: Provider, client: httpx.AsyncClient, *, api_key: str | None = None) -> None:
        try:
            self._url, variable = _ENDPOINTS[provider]
        except KeyError:
            raise ValueError("Choose openai or openrouter as the provider.") from None
        self._api_key = (os.getenv(variable, "") if api_key is None else api_key).strip()
        if not self._api_key:
            raise ValueError(f"Provide an API key or set {variable}.")
        self._provider = provider
        self._client = client

    async def complete_json(
        self, model_id: str, *, instructions: str, prompt: str, media: tuple[ImageInput | VideoInput, ...],
    ) -> Completion:
        model_id = model_id.strip()
        if not model_id:
            raise ValueError("A model ID is required.")
        if self._provider == "openai" and any(isinstance(item, VideoInput) for item in media):
            raise ModelError("Use timestamped image frames for the OpenAI endpoint, or a video model on OpenRouter.")
        content = [{"type": "input_text", "text": prompt}, *map(_media_part, media)]
        payload = {
            "model": model_id,
            "instructions": instructions,
            "input": [{"role": "user", "content": content}],
            "text": {"format": {"type": "json_object"}},
        }
        if self._provider == "openai":
            payload["store"] = False
        try:
            response = await self._client.post(
                self._url, json=payload, headers={"Authorization": f"Bearer {self._api_key}"},
                follow_redirects=False,
            )
        except httpx.TransportError as error:
            raise RetryableModelError(f"{self._provider} transport failed ({type(error).__name__}).") from None
        status = response.status_code
        if status in {408, 429} or 500 <= status < 600:
            raise RetryableModelError(f"{self._provider} returned HTTP {status}.")
        if not response.is_success:
            raise ModelError(f"{self._provider} returned HTTP {status}.")
        return self._parse(response, model_id)

    def _parse(self, response: httpx.Response, requested_model: str) -> Completion:
        try:
            body = response.json()
            if body.get("status") != "completed" or body.get("error"):
                raise ModelError(f"{self._provider} did not complete the request.")
            text = "".join(
                part["text"] for item in body["output"] if item.get("type") == "message"
                for part in item["content"] if part.get("type") == "output_text"
            )
            usage = body.get("usage")
            metrics = ModelUsage(usage.get("input_tokens"), usage.get("output_tokens"), usage.get("cost")) if usage else None
        except (ValueError, AttributeError, KeyError, TypeError):
            raise ModelError(f"{self._provider} returned an invalid response envelope.") from None
        if not text.strip():
            raise ModelError(f"{self._provider} returned no output text.")
        return Completion(text, body.get("model") or requested_model, metrics)
