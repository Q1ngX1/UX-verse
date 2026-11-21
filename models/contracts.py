from dataclasses import dataclass, field
from typing import Literal, Protocol


class ModelError(Exception):
    """A model or provider request failed."""


class RetryableModelError(ModelError):
    """A transient provider failure that the caller may retry."""


@dataclass(frozen=True)
class ModelUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


@dataclass(frozen=True)
class ImageInput:
    data: bytes = field(repr=False)
    mime_type: Literal["image/png", "image/jpeg", "image/webp"] = "image/png"

    def __post_init__(self) -> None:
        if not self.data or self.mime_type not in {"image/png", "image/jpeg", "image/webp"}:
            raise ValueError("Expected a nonempty PNG, JPEG, or WebP image.")


@dataclass(frozen=True)
class VideoInput:
    data: bytes = field(repr=False)
    mime_type: Literal["video/mp4", "video/webm"] = "video/mp4"

    def __post_init__(self) -> None:
        if not self.data or self.mime_type not in {"video/mp4", "video/webm"}:
            raise ValueError("Expected a nonempty MP4 or WebM clip.")


@dataclass(frozen=True)
class Completion:
    text: str
    model_id: str
    usage: ModelUsage | None = None


class ModelProvider(Protocol):
    async def complete_json(
        self, model_id: str, *, instructions: str, prompt: str, media: tuple[ImageInput | VideoInput, ...],
    ) -> Completion:
        ...
