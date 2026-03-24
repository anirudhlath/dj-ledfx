from __future__ import annotations

import asyncio
import time
from collections import deque

from loguru import logger

from dj_ledfx import metrics
from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.effects.deck import EffectDeck
from dj_ledfx.events import EventBus, TransportStateChangedEvent
from dj_ledfx.spatial.pipeline import ScenePipeline
from dj_ledfx.transport import TransportState
from dj_ledfx.types import BeatContext, RenderedFrame


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

    def clear(self) -> None:
        self._frames = [None] * self._capacity
        self._write_index = 0
        self._count = 0


class EffectEngine:
    def __init__(
        self,
        clock: BeatClock,
        deck: EffectDeck,
        led_count: int,
        fps: int = 60,
        max_lookahead_s: float = 1.0,
        pipelines: list[ScenePipeline] | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._clock = clock
        self._deck = deck
        self._led_count = led_count
        self._fps = fps
        self._frame_period = 1.0 / fps
        self._max_lookahead_s = max_lookahead_s
        self.ring_buffer = RingBuffer(capacity=fps, led_count=led_count)
        self._running = False
        self._last_tick_time = 0.0
        self._render_times: deque[float] = deque(maxlen=fps * 10)
        self._event_bus = event_bus
        self._transport_state = TransportState.STOPPED
        self._resume_event = asyncio.Event()

        # Always maintain a non-empty pipelines list: build a default pipeline
        # from the engine's own deck and ring_buffer when none are provided.
        if pipelines:
            self.pipelines: list[ScenePipeline] = pipelines
        else:
            default_pipeline = ScenePipeline(
                scene_id="__default__",
                deck=deck,
                ring_buffer=self.ring_buffer,
                compositor=None,
                mapping=None,
                devices=[],
                led_count=led_count,
            )
            self.pipelines = [default_pipeline]

    @property
    def avg_render_time_ms(self) -> float:
        if not self._render_times:
            return 0.0
        return sum(self._render_times) / len(self._render_times) * 1000.0

    @property
    def transport_state(self) -> TransportState:
        return self._transport_state

    def set_transport_state(self, state: TransportState) -> None:
        old = self._transport_state
        if old == state:
            return
        self._transport_state = state
        if state.is_active:
            self._resume_event.set()
        else:
            self._resume_event.clear()
            cleared: set[int] = set()
            for pipeline in self.pipelines:
                buf_id = id(pipeline.ring_buffer)
                if buf_id not in cleared:
                    pipeline.ring_buffer.clear()
                    cleared.add(buf_id)
            buf_id = id(self.ring_buffer)
            if buf_id not in cleared:
                self.ring_buffer.clear()
        if self._event_bus is not None:
            self._event_bus.emit(TransportStateChangedEvent(old_state=old, new_state=state))
        logger.info("Transport: {} → {}", old.value, state.value)

    def tick(self, now: float) -> None:
        target_time = now + self._max_lookahead_s
        state = self._clock.get_state_at(target_time)

        render_start = time.monotonic()

        ctx = BeatContext(
            beat_phase=state.beat_phase,
            bar_phase=state.bar_phase,
            bpm=state.bpm,
            dt=self._frame_period,
        )

        seen_buffers: set[int] = set()
        for pipeline in self.pipelines:
            buf_id = id(pipeline.ring_buffer)
            if buf_id in seen_buffers:
                continue
            seen_buffers.add(buf_id)
            colors = pipeline.deck.render(ctx, pipeline.led_count)
            frame = RenderedFrame(
                colors=colors,
                target_time=target_time,
                beat_phase=state.beat_phase,
                bar_phase=state.bar_phase,
            )
            pipeline.ring_buffer.write(frame)

        render_elapsed = time.monotonic() - render_start
        metrics.RENDER_DURATION.observe(render_elapsed)
        metrics.FRAMES_RENDERED.inc()
        self._render_times.append(render_elapsed)

        logger.trace(
            "Rendered {} pipeline(s) for t+{:.0f}ms",
            len(self.pipelines),
            self._max_lookahead_s * 1000,
        )

    def add_pipeline(self, pipeline: ScenePipeline) -> None:
        """Add a pipeline to the render loop."""
        self.pipelines.append(pipeline)

    def remove_pipeline(self, scene_id: str) -> None:
        """Remove a pipeline by scene_id and clear its ring buffer."""
        for i, p in enumerate(self.pipelines):
            if p.scene_id == scene_id:
                p.ring_buffer.clear()
                self.pipelines.pop(i)
                return

    def stop(self) -> None:
        self._running = False
        self._resume_event.set()

    async def run(self) -> None:
        self._running = True
        metrics.RENDER_FPS.set(self._fps)
        logger.info(
            "EffectEngine started: {}fps, {}ms lookahead, {} LEDs",
            self._fps,
            int(self._max_lookahead_s * 1000),
            self._led_count,
        )

        while self._running:
            await self._resume_event.wait()
            self._last_tick_time = time.monotonic()
            while self._running and self._resume_event.is_set():
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
