from __future__ import annotations

import asyncio
import time

import numpy as np
from loguru import logger

from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.effects.base import Effect
from dj_ledfx.types import RenderedFrame


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


class EffectEngine:
    def __init__(
        self,
        clock: BeatClock,
        effect: Effect,
        led_count: int,
        fps: int = 60,
        max_lookahead_s: float = 1.0,
    ) -> None:
        self._clock = clock
        self._effect = effect
        self._led_count = led_count
        self._fps = fps
        self._frame_period = 1.0 / fps
        self._max_lookahead_s = max_lookahead_s
        self.ring_buffer = RingBuffer(capacity=fps, led_count=led_count)
        self._running = False
        self._last_tick_time = 0.0
        self._render_times: list[float] = []

    @property
    def avg_render_time_ms(self) -> float:
        if not self._render_times:
            return 0.0
        return sum(self._render_times) / len(self._render_times) * 1000.0

    def tick(self, now: float) -> None:
        target_time = now + self._max_lookahead_s
        state = self._clock.get_state_at(target_time)

        render_start = time.monotonic()
        colors = self._effect.render(
            beat_phase=state.beat_phase,
            bar_phase=state.bar_phase,
            dt=self._frame_period,
            led_count=self._led_count,
        )
        render_elapsed = time.monotonic() - render_start

        self._render_times.append(render_elapsed)
        if len(self._render_times) > 600:
            self._render_times.pop(0)

        frame = RenderedFrame(
            colors=colors,
            target_time=target_time,
            beat_phase=state.beat_phase,
            bar_phase=state.bar_phase,
        )
        self.ring_buffer.write(frame)
        logger.trace("Rendered frame for t+{:.0f}ms", self._max_lookahead_s * 1000)

    def stop(self) -> None:
        self._running = False

    async def run(self) -> None:
        self._running = True
        self._last_tick_time = time.monotonic()
        logger.info(
            "EffectEngine started: {}fps, {}ms lookahead, {} LEDs",
            self._fps,
            int(self._max_lookahead_s * 1000),
            self._led_count,
        )

        while self._running:
            now = time.monotonic()
            self.tick(now)

            self._last_tick_time += self._frame_period
            sleep_time = self._last_tick_time + self._frame_period - time.monotonic()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            else:
                self._last_tick_time = time.monotonic()
                await asyncio.sleep(0)

        logger.info("EffectEngine stopped")
