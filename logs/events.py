import json
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_serializer, field_validator

CURRENT_SCHEMA_VERSION = 1
NonEmptyString = Annotated[str, Field(min_length=1)]


class _Event(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True, strict=True)

    event: NonEmptyString
    timestamp: AwareDatetime

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_timestamp(cls, value: object) -> object:
        return datetime.fromisoformat(value) if isinstance(value, str) else value

    @field_serializer("timestamp")
    def format_timestamp(self, value: datetime) -> str:
        return value.isoformat()


class LegacyEvent(_Event):
    """An event written before run-level metadata was introduced."""

    schema_version: Literal[0] = 0


class RunEvent(_Event):
    """Versioned envelope with additive, source-defined event fields."""

    schema_version: Literal[1]
    run_id: NonEmptyString
    seq: Annotated[int, Field(ge=1)]
    source: NonEmptyString
    decision_id: NonEmptyString | None = None
    action_id: NonEmptyString | None = None
    observation_id: NonEmptyString | None = None
    before_observation_id: NonEmptyString | None = None


EventRecord = LegacyEvent | RunEvent


class UnsupportedEventVersion(ValueError):
    """The log needs a reader that understands its schema version."""


def parse_event(line: str) -> EventRecord:
    row = json.loads(line)
    if not isinstance(row, dict):
        raise ValueError("Expected a JSON object for a log event.")
    version = row.get("schema_version", 0)
    if type(version) is not int:
        raise ValueError("The event schema version must be an integer.")
    if version == 0:
        return LegacyEvent.model_validate(row)
    if version == CURRENT_SCHEMA_VERSION:
        return RunEvent.model_validate(row)
    raise UnsupportedEventVersion(f"Unsupported event schema version: {version}.")
