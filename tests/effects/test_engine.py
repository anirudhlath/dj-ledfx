import asyncio
import time
from unittest.mock import MagicMock

import numpy as np
import pytest

import dj_ledfx.metrics as metrics_mod
from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.effects.engine import EffectEngine, RingBuffer
from dj_ledfx.looks.builtin import builtin_looks
from dj_ledfx.types import RenderedFrame
from dj_ledfx.zones.runtime import ZoneLight, ZoneRuntime


@pytest.fixture
def clock() -> BeatClock:
    c = BeatClock()
    now = time.monotonic()
    c.on_beat(bpm=120.0, beat_number=1, next_beat_ms=500, timestamp=now)
    return c


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


def _runtime(zone_id: str, clock: BeatClock) -> ZoneRuntime:
    look = next(look for look in builtin_looks() if look.id == "classic-breathe")
    light = ZoneLight(f"{zone_id}-light", 4, DeviceCapabilities(protocol="LIFX"))
    return ZoneRuntime(zone_id, look, [light], clock=clock, latency_s=lambda _: 0.05)


def test_the_engine_renders_each_zone_it_hosts(clock: BeatClock) -> None:
    engine = EffectEngine(fps=60)
    desk, shelf = _runtime("desk", clock), _runtime("shelf", clock)
    engine.add_runtime(desk)
    engine.add_runtime(shelf)
    now = time.monotonic()

    engine.tick(now)
    engine.remove_runtime("shelf")
    engine.tick(now + 1 / 60)

    assert (desk.ring.count, shelf.ring.count) == (2, 1)
    frame = desk.ring.find_nearest(now + 0.05 + 1 / 60)
    assert frame is not None
    assert (frame.colors.shape, frame.colors.dtype) == ((4, 3), np.float32)
    assert engine.fill_level == desk.ring.fill_level
    assert EffectEngine().fill_level == 1.0


def test_a_tick_observes_the_render_duration(
    clock: BeatClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    duration, rendered = MagicMock(), MagicMock()
    monkeypatch.setattr(metrics_mod, "RENDER_DURATION", duration)
    monkeypatch.setattr(metrics_mod, "FRAMES_RENDERED", rendered)
    engine = EffectEngine(fps=60)
    engine.add_runtime(_runtime("desk", clock))

    engine.tick(time.monotonic())

    duration.observe.assert_called_once()
    rendered.inc.assert_called_once()
    assert engine.avg_render_time_ms > 0.0


async def test_the_engine_renders_until_stopped(clock: BeatClock) -> None:
    engine = EffectEngine(fps=60)
    desk = _runtime("desk", clock)
    engine.add_runtime(desk)

    task = asyncio.create_task(engine.run())
    await asyncio.sleep(0.1)
    engine.stop()
    await asyncio.wait_for(task, timeout=1.0)

    assert desk.ring.count >= 3
