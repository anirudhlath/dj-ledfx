from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import TYPE_CHECKING

from loguru import logger

from dj_ledfx import metrics
from dj_ledfx.types import RenderedFrame

if TYPE_CHECKING:
    from dj_ledfx.zones.runtime import ZoneRuntime  # imports RingBuffer from this module


class RingBuffer:
    def __init__(self, capacity: int, led_count: int) -> None:
        self._capacity = capacity
        self._led_count = led_count
        self._frames: list[RenderedFrame | None] = [None] * capacity
        self._write_index = 0
        self._count = 0

    @property
    def count(self) -> int:
        return self._count

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def led_count(self) -> int:
        return self._led_count

    def write(self, frame: RenderedFrame) -> None:
        self._frames[self._write_index] = frame
        self._write_index = (self._write_index + 1) % self._capacity
        if self._count < self._capacity:
            self._count += 1

    def find_nearest(self, target_time: float) -> RenderedFrame | None:
        best: RenderedFrame | None = None
        best_diff = float("inf")

        for frame in self._frames:
            if frame is None:
                continue
            diff = abs(frame.target_time - target_time)
            if diff < best_diff:
                best_diff = diff
                best = frame

        if best is None:
            return None

        return RenderedFrame(
            colors=best.colors.copy(),
            target_time=best.target_time,
            beat_phase=best.beat_phase,
            bar_phase=best.bar_phase,
        )

    @property
    def fill_level(self) -> float:
        return self._count / self._capacity

    def clear(self) -> None:
        self._frames = [None] * self._capacity
        self._write_index = 0
        self._count = 0


class EffectEngine:
    """Renders every running zone once a frame (spec §4.1).

    The zone manager adds and removes the zones' runtimes: this is its RuntimeHost. Each
    runtime renders for now plus its own horizon into its own ring buffer.
    """

    def __init__(self, fps: int = 60) -> None:
        self._fps = fps
        self._frame_period = 1.0 / fps
        self._runtimes: dict[str, ZoneRuntime] = {}
        self._running = False
        self._render_times: deque[float] = deque(maxlen=fps * 10)

    @property
    def avg_render_time_ms(self) -> float:
        if not self._render_times:
            return 0.0
        return sum(self._render_times) / len(self._render_times) * 1000.0

    @property
    def fill_level(self) -> float:
        """The emptiest running zone's ring buffer fill; 1.0 when nothing runs."""
        return min((runtime.ring.fill_level for runtime in self._runtimes.values()), default=1.0)

    def add_runtime(self, runtime: ZoneRuntime) -> None:
        self._runtimes[runtime.zone_id] = runtime

    def remove_runtime(self, zone_id: str) -> None:
        self._runtimes.pop(zone_id, None)

    def tick(self, now: float) -> None:
        started = time.monotonic()
        for runtime in self._runtimes.values():
            runtime.tick(now)
        elapsed = time.monotonic() - started
        metrics.RENDER_DURATION.observe(elapsed)
        metrics.FRAMES_RENDERED.inc()
        self._render_times.append(elapsed)

    def stop(self) -> None:
        self._running = False

    async def run(self) -> None:
        self._running = True
        metrics.RENDER_FPS.set(self._fps)
        logger.info("EffectEngine started: {} fps", self._fps)
        next_tick = time.monotonic()
        while self._running:
            self.tick(time.monotonic())
            next_tick += self._frame_period
            delay = next_tick - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            else:  # fell behind: count from now rather than burst to catch up
                next_tick = time.monotonic()
                await asyncio.sleep(0)
        logger.info("EffectEngine stopped")
