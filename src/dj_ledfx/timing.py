"""Time helpers shared across the app: UTC timestamps, the one-second rate window and
the fixed-period loop the engine and the scheduler run."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections import deque

RATE_WINDOW_S = 1.0  # rates (frames sent, frames rendered) cover the last second


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    """A saved timestamp without a timezone is UTC."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def trim_window(stamps: deque[float], now: float) -> None:
    """Drop the stamps older than the rate window, so len(stamps) is a rate per second."""
    while stamps and now - stamps[0] > RATE_WINDOW_S:
        stamps.popleft()


async def paced(
    period_s: float, step: Callable[[float], None], running: Callable[[], bool]
) -> None:
    """Call step(now) every period_s while running() says so. A late step restarts the
    count from now rather than bursting to catch up."""
    next_tick = time.monotonic()
    while running():
        step(time.monotonic())
        next_tick += period_s
        delay = next_tick - time.monotonic()
        if delay > 0:
            await asyncio.sleep(delay)
        else:
            next_tick = time.monotonic()
            await asyncio.sleep(0)
