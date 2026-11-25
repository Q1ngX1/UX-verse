import argparse
import asyncio
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from playwright.async_api import Error

from .actions import ACTION_LIST, Navigate
from .worker import browser_worker


async def run(target: Navigate, action_file: Path | None, output: Path, headed: bool, record_input: bool = False) -> None:
    actions = ACTION_LIST.validate_json(action_file.read_bytes()) if action_file else []
    async with browser_worker(target.url, output, headed=headed, record_input=record_input) as worker:
        await worker.execute(target)
        for action in actions:
            await worker.execute(action)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a scripted UX-verse browser session.")
    parser.add_argument("url", help="Start page on the target origin")
    parser.add_argument("--actions", type=Path, help="JSON file with browser actions after navigation")
    parser.add_argument("--output", type=Path, help="New directory for session evidence")
    parser.add_argument("--headed", action="store_true", help="Show the Chromium window")
    parser.add_argument("--record-input", action="store_true", help="Record live page video, pointer and keyboard input")
    args = parser.parse_args()
    run_id = f"{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid4().hex[:8]}"
    output = args.output or Path("runs", run_id)
    try:
        asyncio.run(run(Navigate(url=args.url), args.actions, output, args.headed, args.record_input))
    except TimeoutError:
        parser.exit(1, f"Browser run timed out. Evidence directory: {output.resolve()}\n")
    except (Error, OSError, ValueError) as error:
        parser.exit(1, f"{error}\nEvidence directory: {output.resolve()}\n")
    print(output.resolve())


if __name__ == "__main__":
    main()
