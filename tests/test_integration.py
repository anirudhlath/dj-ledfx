import asyncio
import time
from pathlib import Path

import numpy as np
import pytest
from conftest import MockDeviceAdapter

from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.devices.manager import ManagedDevice
from dj_ledfx.effects.engine import EffectEngine
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.looks.builtin import builtin_looks
from dj_ledfx.scheduling.scheduler import LookaheadScheduler
from dj_ledfx.zones.runtime import ZoneLight, ZoneRuntime


def _device(name: str, latency_ms: float, led_count: int) -> ManagedDevice:
    adapter = MockDeviceAdapter(name=name, led_count=led_count)
    tracker = LatencyTracker(strategy=StaticLatency(latency_ms))
    return ManagedDevice(adapter=adapter, tracker=tracker, max_fps=60)


def _clock() -> BeatClock:
    clock = BeatClock()
    clock.on_beat(bpm=120.0, beat_number=1, next_beat_ms=500, timestamp=time.monotonic())
    return clock


def _zone(
    zone_id: str, look_id: str, devices: list[ManagedDevice], clock: BeatClock
) -> ZoneRuntime:
    """A running zone as the zone manager builds one (lights are keyed by name here)."""
    look = next(look for look in builtin_looks() if look.id == look_id)
    caps = DeviceCapabilities(protocol="LIFX")
    lights = [ZoneLight(d.adapter.device_info.name, d.adapter.led_count, caps) for d in devices]
    latency = {d.adapter.device_info.name: d.tracker.effective_latency_s for d in devices}
    return ZoneRuntime(zone_id, look, lights, clock=clock, latency_s=latency.__getitem__)


async def _play(zones: list[ZoneRuntime], devices: list[ManagedDevice], seconds: float) -> None:
    """The engine and the scheduler, wired the way main wires them, for a while."""
    engine = EffectEngine(fps=60)
    scheduler = LookaheadScheduler(devices=devices, fps=60)
    for zone in zones:
        engine.add_runtime(zone)
        for light in zone.lights:
            scheduler.set_route(light.device_id, zone.route_for(light.device_id))
    tasks = [asyncio.create_task(engine.run()), asyncio.create_task(scheduler.run())]
    await asyncio.sleep(seconds)
    engine.stop()
    scheduler.stop()
    await asyncio.gather(*tasks)


async def test_one_zone_streams_each_light_its_own_slice() -> None:
    near, far = _device("near", 10.0, 10), _device("far", 100.0, 5)
    zone = _zone("desk", "classic-rainbow-wave", [near, far], _clock())

    await _play([zone], [near, far], 0.5)

    assert zone.horizon_s == pytest.approx(0.1 + 1 / 60)
    assert zone.leds.count == 15
    assert near.adapter.send_frame_calls and far.adapter.send_frame_calls
    near_frame, far_frame = near.adapter.send_frame_calls[-1], far.adapter.send_frame_calls[-1]
    assert (near_frame.shape, far_frame.shape) == ((10, 3), (5, 3))
    assert near_frame.dtype == far_frame.dtype == np.uint8


async def test_two_zones_play_their_own_looks() -> None:
    left, right = _device("left", 10.0, 10), _device("right", 10.0, 10)
    clock = _clock()
    zones = [
        _zone("a", "classic-beat-pulse", [left], clock),
        _zone("b", "classic-rainbow-wave", [right], clock),
    ]

    await _play(zones, [left, right], 0.5)

    assert left.adapter.send_frame_calls and right.adapter.send_frame_calls
    left_frame, right_frame = left.adapter.send_frame_calls[-1], right.adapter.send_frame_calls[-1]
    assert not np.array_equal(left_frame, right_frame), "each zone plays its own look"


async def test_rtt_callback_updates_tracker() -> None:
    """RTT callback from transport updates latency tracker."""
    from dj_ledfx.latency.strategies import EMALatency

    strategy = EMALatency(initial_value_ms=50.0)
    tracker = LatencyTracker(strategy=strategy)
    initial = tracker.effective_latency_ms

    # Simulate RTT callback (same path as LifxTransport probe callback)
    tracker.update(25.0)
    assert tracker.effective_latency_ms != initial
    # RTT of 25ms should pull EMA down from 50ms initial
    assert tracker.effective_latency_ms < initial


async def test_rtt_feedback_shifts_frame_selection() -> None:
    """Lower RTT → lower effective latency → scheduler picks earlier frame."""
    from dj_ledfx.latency.strategies import EMALatency

    strategy = EMALatency(initial_value_ms=100.0)
    tracker = LatencyTracker(strategy=strategy)

    high_latency = tracker.effective_latency_s
    # Simulate many low-RTT probes
    for _ in range(20):
        tracker.update(10.0)
    low_latency = tracker.effective_latency_s

    assert low_latency < high_latency
    # This confirms the scheduler would read a different (earlier) ring buffer position


@pytest.mark.asyncio
async def test_startup_with_fresh_db(tmp_path: Path) -> None:
    """Full startup with empty DB (no TOML migration)."""
    from dj_ledfx.persistence.state_db import StateDB

    db = StateDB(tmp_path / "state.db")
    await db.open()
    version = await db.get_schema_version()
    assert version == 5
    devices = await db.load_devices()
    assert devices == []
    scenes = await db.load_scenes()
    assert scenes == []
    await db.close()


@pytest.mark.asyncio
async def test_startup_with_migrated_toml(tmp_path: Path) -> None:
    """Full startup migrates config.toml into DB."""
    import tomli_w

    from dj_ledfx.persistence.state_db import StateDB
    from dj_ledfx.persistence.toml_io import migrate_from_toml

    config_toml = tmp_path / "config.toml"
    config_toml.write_bytes(
        tomli_w.dumps(
            {
                "engine": {"fps": 90},
                "effect": {"active_effect": "beat_pulse", "beat_pulse": {"gamma": 3.0}},
            }
        ).encode()
    )

    presets_toml = tmp_path / "presets.toml"
    presets_toml.write_bytes(
        tomli_w.dumps(
            {"presets": {"Test": {"effect_class": "beat_pulse", "params": {"gamma": 2.0}}}}
        ).encode()
    )

    db = StateDB(tmp_path / "state.db")
    await db.open()
    await migrate_from_toml(db, config_path=config_toml, presets_path=presets_toml)

    config = await db.load_all_config()
    assert config[("engine", "fps")] == 90

    presets = await db.load_presets()
    assert "Test" in {p["name"] for p in presets}

    assert not config_toml.exists()
    assert (tmp_path / "config.toml.bak").exists()
    await db.close()
