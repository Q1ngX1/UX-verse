"""Single-finger swipe planning adapted from phoneos (Apache-2.0).

Source: https://github.com/mbatinefe/phoneos/blob/161910e11976ae88a3e6b000715a1694f3ce9794/src/humanize/humanizer.ts
See licenses/phoneos-Apache-2.0.txt. This Python adaptation uses Python's
seeded RNG and preserves requested endpoints for reproducible browser tests.
"""

from argparse import ArgumentParser
from math import hypot
from random import Random
from typing import Literal, get_args

TouchMotion = Literal["linear", "phoneos-flick", "phoneos-drag"]
Point = tuple[int, int]


def add_touch_motion_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("--touch-motion", choices=get_args(TouchMotion), default="linear",
                        help="Trajectory for mobile swipe actions")
    parser.add_argument("--touch-seed", type=int, default=0, help="Seed for phoneos swipe plans")


def phoneos_swipe_steps(
    start: Point, end: Point, *, flick: bool, viewport: Point, rng: Random,
) -> list[tuple[Point, float]]:
    """Return viewport points and scheduled seconds between touch moves."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    perpendicular_scale = max(1, hypot(dx, dy))

    def control(fraction: float) -> tuple[float, float]:
        # phoneos natural profile uses a 5% perpendicular control-point spread.
        return (start[0] + dx * fraction - dy / perpendicular_scale * rng.gauss(0, perpendicular_scale * 0.05),
                start[1] + dy * fraction + dx / perpendicular_scale * rng.gauss(0, perpendicular_scale * 0.05))

    first, second = control(0.3), control(0.7)
    total_ms = min(650, max(280, rng.lognormvariate(0, 0.25) * 420))
    count = rng.randint(10, 16)
    settle_ms = min(160, max(30, rng.lognormvariate(0, 0.3) * (45 if flick else 90)))
    steps = []
    for index in range(1, count + 1):
        t = index / count
        if flick or t < 0.5:
            fraction = t * t * (1 if flick else 2)
        else:
            fraction = 1 - 2 * (1 - t) ** 2
        u = 1 - fraction
        weights = (u**3, 3 * u**2 * fraction, 3 * u * fraction**2, fraction**3)
        point = tuple(round(sum(value * weight for value, weight in zip(axis, weights, strict=True)))
                      for axis in zip(start, first, second, end, strict=True))
        x = min(viewport[0] - 1, max(0, point[0]))
        y = min(viewport[1] - 1, max(0, point[1]))
        delay = (total_ms / count + (settle_ms if index == 1 else 0)) / 1000
        steps.append(((x, y), delay))
    return steps
