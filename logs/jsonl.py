import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Protocol
from uuid import uuid4

from .events import CURRENT_SCHEMA_VERSION, EventRecord, RunEvent, parse_event


class EventSink(Protocol):
    def __call__(self, event: str, /, **fields: object) -> None:
        ...


class RunEvents:
    """Share an identity and event order across the JSONL files of one run."""

    def __init__(self) -> None:
        self._run_id = uuid4().hex
        self._sequence = 0
        self._lock = Lock()

    @contextmanager
    def open_log(self, path: Path, *, source: str) -> Iterator[EventSink]:
        with path.open("x", encoding="utf-8") as stream:
            def emit(event: str, /, **fields: object) -> None:
                with self._lock:
                    header = {
                        "schema_version": CURRENT_SCHEMA_VERSION,
                        "run_id": self._run_id,
                        "seq": self._sequence + 1,
                        "source": source,
                        "event": event,
                        "timestamp": datetime.now(UTC),
                    }
                    if fields.keys() & header.keys():
                        raise ValueError("Event fields overlap with the event header.")
                    record = RunEvent.model_validate({**header, **fields})
                    line = json.dumps(record.model_dump(exclude_unset=True), ensure_ascii=False, allow_nan=False)
                    stream.write(line + "\n")
                    self._sequence += 1
                    stream.flush()

            yield emit


def read_log(path: Path) -> Iterator[EventRecord]:
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield parse_event(line)
