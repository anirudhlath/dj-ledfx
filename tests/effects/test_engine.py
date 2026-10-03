import asyncio
import time
from unittest.mock import MagicMock

import numpy as np
import pytest
from conftest import builtin_look, nearest_frame, ring_route

import dj_ledfx.metrics as metrics_mod
from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.effects.engine import EffectEngine
from dj_ledfx.effects.ring_buffer import RingBuffer
from dj_ledfx.tempo.clock import TempoClock
from dj_ledfx.types import RenderedFrame
from dj_ledfx.zones.runtime import RuntimeEnv, ZoneLight, ZoneRuntime


@pytest.fixture
def clock() -> TempoClock:
    return TempoClock()  # the internal clock at 120 BPM, as the app starts


def _around(buf: RingBuffer, target_time: float) -> tuple[float, float, float] | None:
    """The times of the frames either side of target_time, and how far it lies between."""
    found = buf.find_around(target_time)
    return None if found is None else (found[0].target_time, found[1].target_time, found[2])


def _write_at(buf: RingBuffer, *times: float) -> None:
    for t in times:
        colors = np.zeros((1, 3), dtype=np.float32)
        buf.write(RenderedFrame(colors=colors, target_time=t, beat_phase=0.0, bar_phase=0.0))


def test_the_ring_finds_the_frames_either_side_of_a_moment_by_their_times() -> None:
    buf = RingBuffer(capacity=10)
    _write_at(buf, 10.0, 11.0, 10.5)  # a horizon that shrank: 10.5 written last
    assert _around(buf, 10.75) == (10.5, 11.0, 0.5)
    assert _around(buf, 10.1) == (10.0, 10.5, pytest.approx(0.2))
    wrapped = RingBuffer(capacity=4)
    _write_at(wrapped, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0)  # it holds 5, 6, 3, 4
    assert _around(wrapped, 5.5) == (5.0, 6.0, 0.5)
    assert _around(wrapped, 4.5) == (4.0, 5.0, 0.5)


def test_a_moment_outside_the_ring_s_frames_gets_the_nearest_frame_alone() -> None:
    buf = RingBuffer(capacity=10)
    assert _around(buf, 10.0) is None
    _write_at(buf, 10.0, 11.0)
    assert _around(buf, 9.0) == (10.0, 10.0, 0.0)  # a look's first frames
    assert _around(buf, 12.0) == (11.0, 11.0, 0.0)  # a light slower than the horizon
    assert _around(buf, 11.0) == (11.0, 11.0, 0.0)  # a moment on a frame


# E5: the ring hands out the frames it holds, and a route's colours are a new 8-bit array,
# so a send never shares the ring's memory, on a frame or between two.
def test_ring_buffer_hands_out_its_frame_and_routes_copy_their_slice() -> None:
    buf = RingBuffer(capacity=10)
    colors = np.full((5, 3), 0.5, dtype=np.float32)
    later = np.full((5, 3), 0.25, dtype=np.float32)
    frame = RenderedFrame(colors=colors, target_time=100.0, beat_phase=0.0, bar_phase=0.0)
    buf.write(frame)
    buf.write(RenderedFrame(colors=later, target_time=101.0, beat_phase=0.0, bar_phase=0.0))
    found = buf.find_around(100.0)
    assert found is not None and found[0] is frame

    for at in (100.0, 100.5):  # on a frame, and between two
        for led_count in (3, 4):  # the slice's size, and a device with more LEDs
            sent = ring_route(buf, start=1, stop=4).colors_at(at, led_count)
            assert sent is not None
            assert not np.shares_memory(sent, colors) and not np.shares_memory(sent, later)
            sent[:] = 0
    assert np.all(colors == 0.5) and np.all(later == 0.25)


def _runtime(zone_id: str, clock: TempoClock) -> ZoneRuntime:
    look = builtin_look("classic-breathe")
    light = ZoneLight(f"{zone_id}-light", 4, DeviceCapabilities(protocol="LIFX"))
    return ZoneRuntime(zone_id, look, [light], RuntimeEnv(clock, lambda _: 0.05))


def test_the_engine_renders_each_zone_it_hosts(clock: TempoClock) -> None:
    engine = EffectEngine(fps=60)
    desk, shelf = _runtime("desk", clock), _runtime("shelf", clock)
    engine.add_runtime(desk)
    engine.add_runtime(shelf)
    now = time.monotonic()

    engine.tick(now)
    engine.remove_runtime(shelf)
    engine.tick(now + 1 / 60)

    assert (desk.ring.count, shelf.ring.count) == (2, 1)
    frame = nearest_frame(desk.ring, now + 0.05 + 1 / 60)
    assert (frame.colors.shape, frame.colors.dtype) == ((4, 3), np.float32)
    assert engine.fill_level == desk.ring.fill_level
    assert EffectEngine().fill_level == 1.0


def test_a_tick_observes_the_render_duration(
    clock: TempoClock, monkeypatch: pytest.MonkeyPatch
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


async def test_the_engine_renders_until_stopped(clock: TempoClock) -> None:
    engine = EffectEngine(fps=60)
    desk = _runtime("desk", clock)
    engine.add_runtime(desk)

    task = asyncio.create_task(engine.run())
    await asyncio.sleep(0.1)
    engine.stop()
    await asyncio.wait_for(task, timeout=1.0)

    assert desk.ring.count >= 3


# M2 review A3: runtimes are kept by identity, so a preview of a zone never replaces it.
def test_a_preview_renders_beside_its_zone(clock: TempoClock) -> None:
    engine = EffectEngine(fps=60)
    desk, preview = _runtime("desk", clock), _runtime("desk", clock)
    engine.add_runtime(desk)
    engine.add_runtime(preview)
    now = time.monotonic()

    engine.tick(now)
    engine.remove_runtime(preview)
    engine.remove_runtime(preview)  # twice is fine
    engine.tick(now + 1 / 60)

    assert (desk.ring.count, preview.ring.count) == (2, 1)
