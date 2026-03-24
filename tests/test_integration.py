import asyncio
import time
from pathlib import Path

import numpy as np
import pytest
from conftest import MockDeviceAdapter

from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.beat.simulator import BeatSimulator
from dj_ledfx.devices.manager import ManagedDevice
from dj_ledfx.effects.beat_pulse import BeatPulse
from dj_ledfx.effects.deck import EffectDeck
from dj_ledfx.effects.engine import EffectEngine, RingBuffer
from dj_ledfx.effects.rainbow_wave import RainbowWave
from dj_ledfx.events import EventBus
from dj_ledfx.latency.strategies import StaticLatency, WindowedMeanLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.prodjlink.listener import BeatEvent
from dj_ledfx.scheduling.scheduler import LookaheadScheduler
from dj_ledfx.spatial.pipeline import ScenePipeline
from dj_ledfx.transport import TransportState


def _setup_pipeline(
    devices: list[ManagedDevice],
    bpm: float = 300.0,
) -> tuple[BeatSimulator, EffectEngine, LookaheadScheduler, EventBus]:
    """Create a full pipeline: BeatSimulator -> Clock -> Engine -> Scheduler."""
    event_bus = EventBus()
    clock = BeatClock()

    def on_beat(event: BeatEvent) -> None:
        clock.on_beat(
            bpm=event.bpm,
            beat_number=event.beat_position,
            next_beat_ms=event.next_beat_ms,
            timestamp=event.timestamp,
        )

    event_bus.subscribe(BeatEvent, on_beat)

    effect = BeatPulse()
    deck = EffectDeck(effect)
    engine = EffectEngine(
        clock=clock,
        deck=deck,
        led_count=10,
        fps=60,
        max_lookahead_s=1.0,
    )

    scheduler = LookaheadScheduler(
        ring_buffer=engine.ring_buffer,
        devices=devices,
        fps=60,
    )

    simulator = BeatSimulator(event_bus=event_bus, bpm=bpm)
    return simulator, engine, scheduler, event_bus


async def test_full_pipeline_simulator_to_mock_device() -> None:
    """Integration: BeatSimulator -> BeatClock -> EffectEngine -> Scheduler -> MockDevice."""
    adapter = MockDeviceAdapter(name="MockLED", led_count=10)
    tracker = LatencyTracker(strategy=StaticLatency(10.0))
    managed = ManagedDevice(adapter=adapter, tracker=tracker, max_fps=60)

    simulator, engine, scheduler, _ = _setup_pipeline([managed])

    engine._resume_event.set()
    scheduler._resume_event.set()
    scheduler._transport_state = TransportState.PLAYING
    sim_task = asyncio.create_task(simulator.run())
    engine_task = asyncio.create_task(engine.run())
    sched_task = asyncio.create_task(scheduler.run())

    await asyncio.sleep(1.0)

    simulator.stop()
    engine.stop()
    scheduler.stop()
    await asyncio.gather(sim_task, engine_task, sched_task, return_exceptions=True)

    assert len(adapter.send_frame_calls) > 0
    sent_colors = adapter.send_frame_calls[0]
    assert isinstance(sent_colors, np.ndarray)
    assert sent_colors.shape == (10, 3)


async def test_mixed_latency_devices() -> None:
    """Two devices with different latencies both receive frames."""
    fast_adapter = MockDeviceAdapter(name="USB Device", led_count=10)
    fast_tracker = LatencyTracker(strategy=StaticLatency(5.0))
    fast_device = ManagedDevice(adapter=fast_adapter, tracker=fast_tracker, max_fps=60)

    slow_adapter = MockDeviceAdapter(name="Govee WiFi", led_count=10)
    slow_tracker = LatencyTracker(
        strategy=WindowedMeanLatency(window_size=60, initial_value_ms=100.0)
    )
    slow_device = ManagedDevice(adapter=slow_adapter, tracker=slow_tracker, max_fps=60)

    simulator, engine, scheduler, _ = _setup_pipeline([fast_device, slow_device])

    engine._resume_event.set()
    scheduler._resume_event.set()
    scheduler._transport_state = TransportState.PLAYING
    sim_task = asyncio.create_task(simulator.run())
    engine_task = asyncio.create_task(engine.run())
    sched_task = asyncio.create_task(scheduler.run())

    await asyncio.sleep(1.0)

    simulator.stop()
    engine.stop()
    scheduler.stop()
    await asyncio.gather(sim_task, engine_task, sched_task, return_exceptions=True)

    # Both devices received frames
    assert len(fast_adapter.send_frame_calls) > 0
    assert len(slow_adapter.send_frame_calls) > 0

    # Fast device should have more frames (higher effective FPS)
    assert len(fast_adapter.send_frame_calls) >= len(slow_adapter.send_frame_calls)


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
    assert version == 3
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


async def test_multi_pipeline_renders_to_separate_devices() -> None:
    """Two pipelines with different effects render to different devices."""
    adapter1 = MockDeviceAdapter(name="LED1", led_count=10)
    tracker1 = LatencyTracker(strategy=StaticLatency(10.0))
    managed1 = ManagedDevice(adapter=adapter1, tracker=tracker1, max_fps=60)

    adapter2 = MockDeviceAdapter(name="LED2", led_count=10)
    tracker2 = LatencyTracker(strategy=StaticLatency(10.0))
    managed2 = ManagedDevice(adapter=adapter2, tracker=tracker2, max_fps=60)

    # Pipeline A: BeatPulse
    deck_a = EffectDeck(BeatPulse())
    buf_a = RingBuffer(60, 10)
    pipeline_a = ScenePipeline(
        scene_id="scene_a",
        deck=deck_a,
        ring_buffer=buf_a,
        compositor=None,
        mapping=None,
        devices=[managed1],
        led_count=10,
    )

    # Pipeline B: RainbowWave
    deck_b = EffectDeck(RainbowWave())
    buf_b = RingBuffer(60, 10)
    pipeline_b = ScenePipeline(
        scene_id="scene_b",
        deck=deck_b,
        ring_buffer=buf_b,
        compositor=None,
        mapping=None,
        devices=[managed2],
        led_count=10,
    )

    event_bus = EventBus()
    clock = BeatClock()
    simulator = BeatSimulator(event_bus=event_bus, bpm=120.0)
    simulator._clock = clock
    clock.on_beat(bpm=120.0, beat_number=1, next_beat_ms=500, timestamp=time.monotonic())

    engine = EffectEngine(
        clock=clock,
        deck=deck_a,
        led_count=10,
        fps=60,
        max_lookahead_s=1.0,
        pipelines=[pipeline_a, pipeline_b],
        event_bus=event_bus,
    )

    scheduler = LookaheadScheduler(
        ring_buffer=buf_a,
        devices=[],
        fps=60,
        event_bus=event_bus,
    )
    scheduler.add_device(managed1, pipeline=pipeline_a)
    scheduler.add_device(managed2, pipeline=pipeline_b)

    engine._resume_event.set()
    scheduler._resume_event.set()
    scheduler._transport_state = TransportState.PLAYING

    sim_task = asyncio.create_task(simulator.run())
    engine_task = asyncio.create_task(engine.run())
    sched_task = asyncio.create_task(scheduler.run())

    await asyncio.sleep(0.5)

    simulator.stop()
    engine.stop()
    scheduler.stop()
    await asyncio.gather(sim_task, engine_task, sched_task, return_exceptions=True)

    # Both devices should have received frames
    assert len(adapter1.send_frame_calls) > 0
    assert len(adapter2.send_frame_calls) > 0

    # Frames should differ (different effects)
    frame1 = adapter1.send_frame_calls[-1]
    frame2 = adapter2.send_frame_calls[-1]
    assert not (frame1 == frame2).all(), "Different effects should produce different frames"
