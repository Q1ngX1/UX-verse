import argparse
import asyncio
import json
import os
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
from playwright.async_api import Error as BrowserError

from models.decision import DecisionAdapter, FlatDecision
from models.responses import ResponsesProvider

from .engine import AgentConfig, AgentResult, run_agent


async def _run(args: argparse.Namespace, config: AgentConfig, output: Path, api_key: str | None) -> AgentResult:
    async with httpx.AsyncClient(timeout=config.model_timeout_seconds) as client:
        provider = ResponsesProvider(
            args.provider, client, api_key=api_key, max_output_tokens=args.max_output_tokens,
            response_schema=FlatDecision.model_json_schema() if args.structured_output else None,
        )
        model = DecisionAdapter(provider, args.model, flat_output=args.structured_output)
        return await run_agent(config, model, output, headed=args.headed)


def main(argv: list[str] | None = None, *, api_key: str | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a vision-based UX-verse Explorer.")
    parser.add_argument("url", help="Start page on the target origin")
    parser.add_argument("--task", required=True, help="Task for the Explorer")
    parser.add_argument("--provider", choices=("openrouter", "openai"), default="openrouter")
    parser.add_argument("--model", default=os.getenv("UX_VERSE_DECISION_MODEL"), help="Vision model ID")
    parser.add_argument("--persona", help="Visitor profile or behavioral context")
    parser.add_argument("--max-steps", type=int, default=6, help="Maximum actions after initial navigation")
    parser.add_argument("--max-output-tokens", type=int, default=256, help="Output tokens per model call")
    parser.add_argument("--structured-output", action="store_true", help="Require a model that supports JSON Schema")
    parser.add_argument("--model-timeout", type=float, default=20, help="Seconds per model call")
    parser.add_argument("--output", type=Path, help="New directory for session evidence")
    parser.add_argument("--headed", action="store_true", help="Show the Chromium window")
    args = parser.parse_args(argv)
    if not args.model or not args.model.strip():
        parser.error("Provide --model or set UX_VERSE_DECISION_MODEL.")

    run_id = f"{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid4().hex[:8]}"
    output = args.output or Path("runs", f"agent-{run_id}")
    try:
        config = AgentConfig(
            target=args.url, task=args.task, persona=args.persona,
            max_steps=args.max_steps, model_timeout_seconds=args.model_timeout,
        )
        result = asyncio.run(_run(args, config, output, api_key))
    except (BrowserError, OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps({"output": str(output.resolve()), **asdict(result)}, ensure_ascii=False))
    return 0 if result.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
