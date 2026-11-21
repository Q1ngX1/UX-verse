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


class BrowserSmokeTest(unittest.TestCase):
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

    def run_browser(self, directory, actions):
        script = directory / "actions.json"
        script.write_text(json.dumps(actions), encoding="utf-8")
        output = directory / "run"
        process = subprocess.run(
            [sys.executable, "-m", "browser", self.url, "--actions", str(script), "--output", str(output)],
            capture_output=True, text=True, timeout=30,
        )
        return process, output

    def events(self, output):
        return [json.loads(line) for line in (output / "actions.jsonl").read_text(encoding="utf-8").splitlines()]

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
