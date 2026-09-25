import asyncio
import time
from unittest.mock import MagicMock

import numpy as np
import pytest

import dj_ledfx.metrics as metrics_mod
from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.effects.engine import EffectEngine
from dj_ledfx.effects.ring_buffer import RingBuffer
from dj_ledfx.looks.builtin import builtin_looks
from dj_ledfx.scheduling.route import DeviceRoute
from dj_ledfx.types import RenderedFrame
from dj_ledfx.zones.runtime import ZoneLight, ZoneRuntime


@pytest.fixture
def clock() -> BeatClock:
    c = BeatClock()
    now = time.monotonic()
    c.on_beat(bpm=120.0, beat_number=1, next_beat_ms=500, timestamp=now)
    return c


def test_ring_buffer_write_and_read() -> None:
    buf = RingBuffer(capacity=10)
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
    buf = RingBuffer(capacity=60)
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


# E5: the ring hands out the frame it holds, and a route's colours are a new 8-bit
# array, so a send never shares the ring's memory.
def test_ring_buffer_hands_out_its_frame_and_routes_copy_their_slice() -> None:
    buf = RingBuffer(capacity=10)
    colors = np.full((5, 3), 0.5, dtype=np.float32)
    frame = RenderedFrame(colors=colors, target_time=100.0, beat_phase=0.0, bar_phase=0.0)
    buf.write(frame)
    assert buf.find_nearest(100.0) is frame

    for led_count in (3, 4):  # the slice's size, and a device with more LEDs
        sent = DeviceRoute(ring=buf, start=1, stop=4, streaming=True).colors_at(100.0, led_count)
        assert sent is not None and not np.shares_memory(sent, colors)
        sent[:] = 0
    assert np.all(colors == 0.5)


def test_ring_buffer_empty_returns_none() -> None:
    buf = RingBuffer(capacity=10)
    assert buf.find_nearest(100.0) is None


def _runtime(zone_id: str, clock: BeatClock, key: str | None = None) -> ZoneRuntime:
    look = next(look for look in builtin_looks() if look.id == "classic-breathe")
    light = ZoneLight(f"{zone_id}-light", 4, DeviceCapabilities(protocol="LIFX"))
    return ZoneRuntime(zone_id, look, [light], clock=clock, latency_s=lambda _: 0.05, key=key)


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


def test_a_preview_renders_beside_its_zone(clock: BeatClock) -> None:
    engine = EffectEngine(fps=60)
    desk, preview = _runtime("desk", clock), _runtime("desk", clock, key="preview:p1")
    engine.add_runtime(desk)
    engine.add_runtime(preview)
    now = time.monotonic()

    engine.tick(now)
    engine.remove_runtime("preview:p1")
    engine.tick(now + 1 / 60)

    assert (desk.key, preview.key) == ("desk", "preview:p1")
    assert (desk.ring.count, preview.ring.count) == (2, 1)
