"""Run repeatable, independently checked Explorer journeys against a local vision model."""

import argparse
import asyncio
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from time import monotonic
from typing import get_args
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from playwright.async_api import Error as BrowserError, Page

from agent.engine import AgentConfig, run_agent
from browser.input_devices import ContinuousPointerMode
from browser.viewport import add_viewport_argument
from logs import read_log
from models.decision import FLAT_DECISIONS, DecisionAdapter
from models.local import LocalProvider


@dataclass(frozen=True)
class Case:
    name: str
    start: str
    task: str
    destination: str
    selector: str
    evidence: str
    answer: str | None = None
    typed_on_home: str | None = None


MOCK = (
    Case("parking", "/", "Use the route directory to find and open Fern Creek Loop. Open Parking & access "
         "and report exactly where it says to park.", "/route.html?id=fern-creek",
         "#route-panel p", "Parking is beside the picnic area.", r"\bpicnic area\b"),
    Case("home-search", "/", "Use the homepage search field to search for East Harbor Walk. Open the exact "
         "route and report its distance.", "/route.html?id=harbor-walk",
         ".route-facts dd", "3.2 mi", r"\b3\.2\s*mi(?:les)?\b", typed_on_home="East Harbor Walk"),
    Case("guide-faq", "/guide.html", "Expand 'What do the difficulty labels mean?' and report what "
         "challenging routes combine.", "/guide.html", "details[open] p", "steeper climbs",
         r"(?s)(?=.*longer distance)(?=.*steeper climb)(?=.*uneven terrain)"),
    Case("filter", "/routes.html", "Apply the In the trees quick filter. Leave the results in Grid view "
         "and report that the filter is active.", "/routes.html?terrain=Forest",
         'body:has([data-view="grid"][aria-pressed="true"]) [data-quick="Forest"][aria-pressed="true"]',
         "In the trees"),
)

EXTERNAL = (
    Case("python-lists", "https://docs.python.org/3.12/tutorial/index.html",
         "Open the 'Using Lists as Queues' tutorial section. Report the standard library class it recommends "
         "for efficient appends and pops from both ends.", "/3.12/tutorial/datastructures.html#using-lists-as-queues",
         "#using-lists-as-queues p", "collections.deque", r"\bdeque\b"),
    Case("python-range", "https://docs.python.org/3.12/tutorial/index.html",
         "Open the tutorial section for the range() function. State whether the given end point is included.",
         "/3.12/tutorial/controlflow.html#the-range-function", "#the-range-function p",
         "The given end point is never part of the generated sequence",
         r"(?:not includ|exclud|never part|not part|not included|does not include)"),
    Case("iana-reserved", "https://www.iana.org/domains",
         "Find the IANA-managed Reserved Domains page and report the two example domains named in its Example domains section.",
         "/domains/reserved", "main p, #body p", "example.com",
         r"(?s)(?=.*\bexample\.com\b)(?=.*\bexample\.org\b)"),
    Case("iana-about", "https://www.iana.org/domains/reserved",
         "Use the site's About navigation and report the full name of IANA from the About page.",
         "/about", "main p, #body p", "Internet Assigned Numbers Authority",
         r"\binternet assigned numbers authority\b"),
)


async def inspect(page: Page, case: Case) -> dict[str, bool | str]:
    actual, expected = urlparse(page.url), urlparse(case.destination)
    destination = actual.path.rstrip("/") == expected.path.rstrip("/")
    if expected.query:
        destination &= set(expected.query.split("&")).issubset(actual.query.split("&"))
    # The content check below confirms the section even if a visit reached it by scrolling.
    nodes = page.locator(case.selector).filter(has_text=case.evidence)
    evidence_visible = False
    viewport = page.viewport_size
    if viewport is None:
        raise ValueError("Benchmark inspection requires a fixed page viewport.")
    for node in await nodes.all():
        box = await node.bounding_box(timeout=1500)
        if (box and box["y"] >= 0 and box["y"] + box["height"] <= viewport["height"]
                and box["x"] >= 0 and box["x"] + box["width"] <= viewport["width"]):
            evidence_visible = await node.is_visible()
            if evidence_visible:
                break
    return {"destination": destination, "evidence_visible": evidence_visible, "url": page.url}


class MockHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args: object) -> None:
        pass


def required_actions_match(run_dir: Path, case: Case) -> bool:
    if case.typed_on_home is None:
        return True
    for event in read_log(run_dir / "actions.jsonl"):
        if event.event != "action":
            continue
        fields = event.model_extra or {}
        action = fields["action"]
        if (fields["status"] == "ok" and urlparse(fields["before_url"]).path == "/"
                and action["type"] == "type" and action["text"].casefold() == case.typed_on_home.casefold()):
            return True
    return False


async def run(args: argparse.Namespace, mock_url: str, output: Path) -> None:
    selected = MOCK if args.group == "mock" else EXTERNAL if args.group == "external" else MOCK + EXTERNAL
    if args.case:
        selected = tuple(case for case in selected if case.name in args.case)
    if not selected:
        raise ValueError("No benchmark cases matched.")
    records = []
    async with httpx.AsyncClient(timeout=45, trust_env=False) as client:
        provider = LocalProvider(client, base_url=args.base_url, max_output_tokens=512,
                                 response_schema=FLAT_DECISIONS[args.device].model_json_schema())
        model = DecisionAdapter(provider, args.model, flat_output=True)
        for repeat in range(1, args.repeats + 1):
            for case in selected:
                started = monotonic()
                evidence: dict[str, bool | str] = {}

                async def inspect_final(page: Page) -> None:
                    evidence.update(await inspect(page, case))

                target = mock_url + case.start if case.start.startswith("/") else case.start
                run_dir = output / f"{repeat:02}-{case.name}"
                try:
                    result = await run_agent(
                        AgentConfig(target=target, task=case.task, max_steps=args.steps, model_timeout_seconds=45,
                                    timeout_seconds=args.run_timeout, record_input=args.record_input,
                                    pointer_mode=args.pointer_mode, viewport=args.viewport, device=args.device),
                        model, run_dir, inspect_final=inspect_final,
                    )
                    answer = result.answer or result.reason
                    answer_matches = case.answer is None or re.search(case.answer, answer, re.I) is not None
                    actions_match = required_actions_match(run_dir, case)
                    record = {"result": asdict(result), "answer_matches": answer_matches,
                              "required_actions_match": actions_match,
                              "passed": result.status == "completed" and answer_matches
                              and actions_match and bool(evidence.get("destination"))
                              and bool(evidence.get("evidence_visible"))}
                except (BrowserError, OSError, ValueError) as error:
                    record = {"passed": False, "error": str(error)}
                row = {"repeat": repeat, "case": case.name, "group": "mock" if case in MOCK else "external",
                       "elapsed_seconds": round(monotonic() - started, 2), **record, "page": evidence,
                       "artifacts": run_dir.name}
                records.append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
                (output / "report.json").write_text(json.dumps(
                    {"model": args.model, "steps": args.steps, "run_timeout": args.run_timeout,
                     "record_input": args.record_input, "pointer_mode": args.pointer_mode,
                     "viewport": args.viewport.model_dump(), "device": args.device,
                     "observation": "screenshot", "text_input": "keys", "runs": records},
                    ensure_ascii=False, indent=2,
                ), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", choices=("mock", "external", "all"), default="all")
    parser.add_argument("--case", action="append")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--steps", type=int, default=10)
    parser.add_argument("--run-timeout", type=float, default=180)
    parser.add_argument("--record-input", action="store_true", help="Record live browser video and input events")
    parser.add_argument("--pointer-mode", choices=get_args(ContinuousPointerMode), default="continuous")
    parser.add_argument("--device", choices=("desktop", "mobile"), default="desktop")
    parser.add_argument("--model", default="qwen3-vl-8b-local")
    parser.add_argument("--base-url", default="http://127.0.0.1:8081/v1")
    add_viewport_argument(parser)
    args = parser.parse_args()
    if args.repeats < 1 or not 1 <= args.steps <= 29:
        parser.error("Repeats must be positive and steps must be between 1 and 29.")
    if not 0 < args.run_timeout <= 300:
        parser.error("Run timeout must be greater than zero and at most 300 seconds.")
    root = Path(__file__).resolve().parents[1]
    output = root / "runs" / f"benchmark-{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid4().hex[:6]}"
    output.mkdir(parents=True)
    print(f"Output: {output}", flush=True)
    handler = partial(MockHandler, directory=root / "mock")
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            asyncio.run(run(args, f"http://127.0.0.1:{server.server_port}", output))
        finally:
            server.shutdown()
            thread.join()


if __name__ == "__main__":
    main()
