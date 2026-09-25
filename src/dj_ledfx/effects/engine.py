from __future__ import annotations

import time
from collections import deque
from typing import TYPE_CHECKING

from loguru import logger

from dj_ledfx import metrics
from dj_ledfx.timing import paced

if TYPE_CHECKING:
    from dj_ledfx.zones.runtime import ZoneRuntime


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
        self._runtimes[runtime.key] = runtime

    def remove_runtime(self, key: str) -> None:
        self._runtimes.pop(key, None)

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
        await paced(self._frame_period, self.tick, lambda: self._running)
        logger.info("EffectEngine stopped")
