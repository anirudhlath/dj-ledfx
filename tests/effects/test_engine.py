import importlib
import time
from unittest.mock import MagicMock

import numpy as np
import pytest

import dj_ledfx.metrics as metrics_mod
from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.effects.beat_pulse import BeatPulse
from dj_ledfx.effects.engine import EffectEngine, RingBuffer
from dj_ledfx.types import RenderedFrame


def test_ring_buffer_write_and_read() -> None:
    buf = RingBuffer(capacity=10, led_count=5)
    frame = RenderedFrame(
        colors=np.zeros((5, 3), dtype=np.uint8),
        target_time=100.0,
        beat_phase=0.0,
        bar_phase=0.0,
    )
    buf.write(frame)
    result = buf.find_nearest(100.0)
    assert result is not None
    assert result.target_time == 100.0


def test_ring_buffer_find_nearest() -> None:
    buf = RingBuffer(capacity=60, led_count=5)
    for i in range(10):
        frame = RenderedFrame(
            colors=np.zeros((5, 3), dtype=np.uint8),
            target_time=100.0 + i * 0.0167,
            beat_phase=0.0,
            bar_phase=0.0,
        )
        buf.write(frame)

    result = buf.find_nearest(100.05)
    assert result is not None
    assert abs(result.target_time - 100.05) < 0.02


def test_ring_buffer_returns_copy() -> None:
    buf = RingBuffer(capacity=10, led_count=5)
    colors = np.full((5, 3), 42, dtype=np.uint8)
    frame = RenderedFrame(colors=colors, target_time=100.0, beat_phase=0.0, bar_phase=0.0)
    buf.write(frame)

    result = buf.find_nearest(100.0)
    assert result is not None
    result.colors[0, 0] = 0
    original = buf.find_nearest(100.0)
    assert original is not None
    assert original.colors[0, 0] == 42


def test_ring_buffer_empty_returns_none() -> None:
    buf = RingBuffer(capacity=10, led_count=5)
    assert buf.find_nearest(100.0) is None


@pytest.mark.asyncio
async def test_engine_tick_observes_render_duration() -> None:
    """Verify that EffectEngine.tick() calls metrics.RENDER_DURATION.observe()."""
    importlib.reload(metrics_mod)
    mock_duration = MagicMock()
    mock_rendered = MagicMock()
    original_duration = metrics_mod.RENDER_DURATION
    original_rendered = metrics_mod.FRAMES_RENDERED
    metrics_mod.RENDER_DURATION = mock_duration
    metrics_mod.FRAMES_RENDERED = mock_rendered
    try:
        from dj_ledfx.effects.engine import EffectEngine
        from dj_ledfx.beat.clock import BeatClock
        from dj_ledfx.effects.beat_pulse import BeatPulse
        import time as time_mod

        clock = BeatClock()
        now = time_mod.monotonic()
        clock.on_beat(bpm=120.0, beat_number=1, next_beat_ms=500, timestamp=now)
        effect = BeatPulse()
        engine = EffectEngine(clock=clock, effect=effect, led_count=10, fps=60)
        engine.tick(now)
        mock_duration.observe.assert_called_once()
        mock_rendered.inc.assert_called_once()
    finally:
        metrics_mod.RENDER_DURATION = original_duration
        metrics_mod.FRAMES_RENDERED = original_rendered


def test_engine_render_tick_populates_buffer() -> None:
    clock = BeatClock()
    now = time.monotonic()
    clock.on_beat(bpm=120.0, beat_number=1, next_beat_ms=500, timestamp=now)

    effect = BeatPulse()
    engine = EffectEngine(
        clock=clock,
        effect=effect,
        led_count=10,
        fps=60,
        max_lookahead_s=1.0,
    )

    engine.tick(now)

    frame = engine.ring_buffer.find_nearest(now + 1.0)
    assert frame is not None
    assert frame.colors.shape == (10, 3)
