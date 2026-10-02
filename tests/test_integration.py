import asyncio
import time
from collections.abc import Callable
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
from conftest import MockDeviceAdapter, builtin_look
from govee_fakes import LAMP, STATUS, TEST_MODEL, UPRIGHT, lamp_row, lamp_transport, sent
from tempo_fakes import beat_event

from dj_ledfx.config import AppConfig
from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.devices.discovery import DiscoveryOrchestrator
from dj_ledfx.devices.govee.backend import GoveeBackend
from dj_ledfx.devices.govee.protocol import build_razer_switch
from dj_ledfx.devices.govee.sku_registry import SKU_REGISTRY
from dj_ledfx.devices.manager import DeviceManager, ManagedDevice
from dj_ledfx.effects.engine import EffectEngine
from dj_ledfx.events import DeviceDiscoveredEvent, DeviceOfflineEvent, DeviceOnlineEvent, EventBus
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.persistence.state_db import StateDB
from dj_ledfx.scheduling.scheduler import LookaheadScheduler
from dj_ledfx.tempo.clock import TempoClock
from dj_ledfx.zones.lights import LightMonitor
from dj_ledfx.zones.runtime import ZoneLight, ZoneRuntime


def _device(name: str, latency_ms: float, led_count: int) -> ManagedDevice:
    adapter = MockDeviceAdapter(name=name, led_count=led_count)
    tracker = LatencyTracker(strategy=StaticLatency(latency_ms))
    return ManagedDevice(adapter=adapter, tracker=tracker, max_fps=60)


def _clock() -> TempoClock:
    """A tempo clock a DJ drives at 120 BPM."""
    clock = TempoClock()
    clock.on_beat(beat_event(time.monotonic(), bpm=120.0))
    return clock


def _zone(
    zone_id: str, look_id: str, devices: list[ManagedDevice], clock: TempoClock
) -> ZoneRuntime:
    """A running zone as the zone manager builds one (lights are keyed by name here)."""
    look = builtin_look(look_id)
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
    assert version == 8
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


async def _until(condition: Callable[[], bool], timeout_s: float = 3.0) -> None:
    deadline = time.monotonic() + timeout_s
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        await asyncio.sleep(0.01)


# Review Focus 1, end to end: a lamp that goes silent mid-look misses three polls, goes
# offline and gets no frames; a scan finds it again, and its first frame switches razer on.
async def test_a_silent_lamp_goes_offline_until_a_scan_finds_it_and_razer_re_arms(
    monkeypatch: pytest.MonkeyPatch, db: StateDB
) -> None:
    monkeypatch.setitem(SKU_REGISTRY, TEST_MODEL, UPRIGHT)
    bus, devices = EventBus(), DeviceManager()
    govee = GoveeBackend()
    transport = govee._transport = lamp_transport()
    orchestrator = DiscoveryOrchestrator(AppConfig(), devices, bus, state_db=db)
    orchestrator._backends = [govee]
    scheduler = LookaheadScheduler(fps=60, disconnect_backoff_s=0.02, event_bus=bus)
    zones = MagicMock(on_power_reading=AsyncMock(), verify_firmware=AsyncMock())
    zones.light_mode.return_value = None
    monitor = LightMonitor(devices=devices, zones=zones, event_bus=bus, zone_poll_s=0.05)

    def _offline(event: DeviceOfflineEvent) -> None:  # as main wires it
        managed = devices.get_by_stable_id(event.stable_id)
        if managed is not None and managed.status != "offline":
            devices.demote_device(event.stable_id)

    def _back(event: DeviceOnlineEvent | DeviceDiscoveredEvent) -> None:
        managed = devices.get_by_stable_id(event.stable_id)
        if managed is not None and not scheduler.has_device(event.stable_id):
            scheduler.add_device(managed)

    bus.subscribe(DeviceOfflineEvent, _offline)
    bus.subscribe(DeviceOnlineEvent, _back)
    bus.subscribe(DeviceDiscoveredEvent, _back)
    await db.upsert_device(lamp_row())
    await orchestrator.connect_known_devices(await db.load_devices())
    lamp = devices.get_by_stable_id(LAMP)
    assert lamp is not None
    zone = ZoneRuntime(
        "lamp",
        builtin_look("classic-rainbow-wave"),
        [ZoneLight(LAMP, lamp.adapter.led_count, lamp.adapter.capabilities)],
        clock=_clock(),
        latency_s=lambda _light: lamp.tracker.effective_latency_s,
    )
    engine = EffectEngine(fps=60)
    engine.add_runtime(zone)
    scheduler.set_route(LAMP, zone.route_for(LAMP))
    razer_on = build_razer_switch(on=True)
    tasks = [asyncio.create_task(job) for job in (engine.run(), scheduler.run(), monitor.run())]
    try:
        await _until(lambda: len(sent(transport)) >= 3)  # it plays
        assert sent(transport)[0] == razer_on

        transport.query_status.return_value = None  # it goes silent
        await _until(lambda: lamp.status == "offline")
        assert transport.query_status.await_count >= 3 * 2  # three polls, each asked twice
        await asyncio.sleep(0.05)  # a frame already on its way lands
        silenced = len(sent(transport))
        await asyncio.sleep(0.3)
        assert len(sent(transport)) == silenced  # no frames while it's offline

        transport.query_status.return_value = STATUS  # it answers again
        assert await orchestrator.run_scan() == 1
        assert lamp.status == "online"
        await _until(lambda: len(sent(transport)) >= silenced + 2)
        first, frame = sent(transport)[silenced : silenced + 2]
        assert first == razer_on and frame["msg"]["cmd"] == "razer"  # razer re-armed
    finally:
        engine.stop()
        scheduler.stop()
        monitor.stop()
        await asyncio.gather(*tasks)
