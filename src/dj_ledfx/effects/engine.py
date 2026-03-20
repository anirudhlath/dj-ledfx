from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import TYPE_CHECKING

from loguru import logger

from dj_ledfx import metrics
from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.effects.deck import EffectDeck
from dj_ledfx.types import RenderedFrame

if TYPE_CHECKING:
    from dj_ledfx.spatial.pipeline import ScenePipeline


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
        deck: EffectDeck,
        led_count: int,
        fps: int = 60,
        max_lookahead_s: float = 1.0,
        pipelines: list[ScenePipeline] | None = None,
    ) -> None:
        self._clock = clock
        self._deck = deck
        self._led_count = led_count
        self._fps = fps
        self._frame_period = 1.0 / fps
        self._max_lookahead_s = max_lookahead_s
        self.ring_buffer = RingBuffer(capacity=fps, led_count=led_count)
        self.pipelines: list[ScenePipeline] = pipelines or []
        self._running = False
        self._last_tick_time = 0.0
        self._render_times: deque[float] = deque(maxlen=fps * 10)

    @property
    def avg_render_time_ms(self) -> float:
        if not self._render_times:
            return 0.0
        return sum(self._render_times) / len(self._render_times) * 1000.0

    def tick(self, now: float) -> None:
        target_time = now + self._max_lookahead_s
        state = self._clock.get_state_at(target_time)

        render_start = time.monotonic()

        if self.pipelines:
            for pipeline in self.pipelines:
                colors = pipeline.deck.render(
                    beat_phase=state.beat_phase,
                    bar_phase=state.bar_phase,
                    dt=self._frame_period,
                    led_count=pipeline.led_count,
                )
                frame = RenderedFrame(
                    colors=colors,
                    target_time=target_time,
                    beat_phase=state.beat_phase,
                    bar_phase=state.bar_phase,
                )
                pipeline.ring_buffer.write(frame)
        else:
            colors = self._deck.render(
                beat_phase=state.beat_phase,
                bar_phase=state.bar_phase,
                dt=self._frame_period,
                led_count=self._led_count,
            )
            frame = RenderedFrame(
                colors=colors,
                target_time=target_time,
                beat_phase=state.beat_phase,
                bar_phase=state.bar_phase,
            )
            self.ring_buffer.write(frame)

        render_elapsed = time.monotonic() - render_start
        metrics.RENDER_DURATION.observe(render_elapsed)
        metrics.FRAMES_RENDERED.inc()
        self._render_times.append(render_elapsed)

        logger.trace(
            "Rendered {} for t+{:.0f}ms",
            f"{len(self.pipelines)} pipeline(s)" if self.pipelines else "frame",
            self._max_lookahead_s * 1000,
        )

    def stop(self) -> None:
        self._running = False

    async def run(self) -> None:
        self._running = True
        metrics.RENDER_FPS.set(self._fps)
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
            sleep_time = self._last_tick_time - time.monotonic()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            else:
                self._last_tick_time = time.monotonic()
                await asyncio.sleep(0)

        logger.info("EffectEngine stopped")
