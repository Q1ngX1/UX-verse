import argparse
import re

from pydantic import BaseModel, ConfigDict, Field


class Viewport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    width: int = Field(default=1280, ge=1, le=3840, strict=True)
    height: int = Field(default=720, ge=1, le=3840, strict=True)


def parse_viewport(value: str) -> Viewport:
    match = re.fullmatch(r"([0-9]{1,4})[xX]([0-9]{1,4})", value)
    if match:
        width, height = map(int, match.groups())
        if 1 <= width <= 3840 and 1 <= height <= 3840:
            return Viewport(width=width, height=height)
    raise argparse.ArgumentTypeError("Use WIDTHxHEIGHT with both dimensions between 1 and 3840.")


def add_viewport_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--viewport", type=parse_viewport, default=Viewport(), metavar="WIDTHxHEIGHT",
                        help="Page viewport in CSS pixels (default: 1280x720)")
