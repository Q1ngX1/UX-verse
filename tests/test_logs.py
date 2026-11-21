import json
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from logs import LegacyEvent, RunEvent, RunEvents, UnsupportedEventVersion, parse_event, read_log


class RunEventsTest(unittest.TestCase):
    def test_independent_runs_and_non_overwriting_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "first.jsonl"
            run = RunEvents()
            with run.open_log(path, source="agent") as emit:
                with self.assertRaisesRegex(ValueError, "event header"):
                    emit("invalid", run_id="overridden")
                emit("sample", detail="测试")
                first = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(first["detail"], "测试")
                self.assertEqual(first["seq"], 1)
                self.assertEqual(first["schema_version"], 1)
            with self.assertRaises(FileExistsError):
                with run.open_log(path, source="browser"):
                    self.fail("Existing logs must be preserved.")

            other_path = Path(directory) / "second.jsonl"
            with RunEvents().open_log(other_path, source="browser") as emit:
                emit("sample")
            second = json.loads(other_path.read_text(encoding="utf-8"))
            self.assertEqual(second["seq"], 1)
            self.assertNotEqual(first["run_id"], second["run_id"])

    def test_reader_preserves_unversioned_and_extended_events(self):
        legacy = {"event": "action", "timestamp": "2026-11-21T07:00:00+00:00", "step": 1}
        current = {
            "schema_version": 1,
            "event": "frame_captured",
            "timestamp": "2026-11-21T07:00:01+00:00",
            "run_id": "run-one",
            "source": "capture",
            "seq": 3,
            "action_id": "action-one",
            "frame": {"relative_ms": 250, "path": "frames/001.png"},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            path.write_text(f"{json.dumps(legacy)}\n\n{json.dumps(current)}\n", encoding="utf-8")
            first, second = read_log(path)
        self.assertIsInstance(first, LegacyEvent)
        self.assertIsInstance(second, RunEvent)
        self.assertEqual(first.model_dump(exclude_unset=True), legacy)
        self.assertEqual(second.model_dump(exclude_unset=True), current)

    def test_reader_rejects_unsupported_or_invalid_schema(self):
        with self.assertRaisesRegex(UnsupportedEventVersion, "version: 2"):
            parse_event('{"schema_version":2}')
        with self.assertRaisesRegex(ValueError, "must be an integer"):
            parse_event('{"schema_version":true}')
        with self.assertRaises(ValidationError):
            parse_event('{"schema_version":1,"event":"action","timestamp":"2026-11-21T07:00:00+00:00"}')
