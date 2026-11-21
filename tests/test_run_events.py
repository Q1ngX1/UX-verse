import json
import tempfile
import unittest
from pathlib import Path

from run_events import RunEvents


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
