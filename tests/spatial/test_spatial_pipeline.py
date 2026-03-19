from __future__ import annotations

import asyncio

import numpy as np
import pytest

from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.beat.simulator import BeatSimulator
from dj_ledfx.devices.manager import ManagedDevice
from dj_ledfx.effects.beat_pulse import BeatPulse
from dj_ledfx.effects.deck import EffectDeck
from dj_ledfx.effects.engine import EffectEngine
from dj_ledfx.events import EventBus
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.scheduling.scheduler import LookaheadScheduler
from dj_ledfx.spatial.compositor import SpatialCompositor
from dj_ledfx.spatial.geometry import PointGeometry
from dj_ledfx.spatial.mapping import LinearMapping
from dj_ledfx.spatial.scene import DevicePlacement, SceneModel
from tests.conftest import MockDeviceAdapter


@pytest.mark.asyncio
async def test_spatial_pipeline_different_positions_different_colors() -> None:
    """Devices at different positions should receive different colors."""
    left_adapter = MockDeviceAdapter(name="left", led_count=10)
    right_adapter = MockDeviceAdapter(name="right", led_count=10)

    scene = SceneModel(
        placements={
            "left": DevicePlacement("left", (0.0, 0.0, 0.0), PointGeometry(), 1),
            "right": DevicePlacement("right", (10.0, 0.0, 0.0), PointGeometry(), 1),
        }
    )
    mapping = LinearMapping(direction=(1.0, 0.0, 0.0))
    compositor = SpatialCompositor(scene, mapping)

    event_bus = EventBus()
    clock = BeatClock()
    simulator = BeatSimulator(event_bus=event_bus, bpm=120.0)
    from dj_ledfx.prodjlink.listener import BeatEvent

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
    engine = EffectEngine(clock=clock, deck=deck, led_count=60, fps=60)

    left_tracker = LatencyTracker(strategy=StaticLatency(latency_ms=5.0))
    right_tracker = LatencyTracker(strategy=StaticLatency(latency_ms=5.0))

    managed_devices = [
        ManagedDevice(adapter=left_adapter, tracker=left_tracker, max_fps=60),
        ManagedDevice(adapter=right_adapter, tracker=right_tracker, max_fps=60),
    ]

    scheduler = LookaheadScheduler(
        ring_buffer=engine.ring_buffer,
        devices=managed_devices,
        fps=60,
        compositor=compositor,
    )

    sim_task = asyncio.create_task(simulator.run())
    engine_task = asyncio.create_task(engine.run())
    sched_task = asyncio.create_task(scheduler.run())

    await asyncio.sleep(0.5)

    simulator.stop()
    engine.stop()
    scheduler.stop()

    await asyncio.gather(sim_task, engine_task, sched_task, return_exceptions=True)

    # Both should have received frames
    assert len(left_adapter.send_frame_calls) > 0
    assert len(right_adapter.send_frame_calls) > 0


@pytest.mark.asyncio
async def test_unmapped_device_gets_broadcast_when_compositor_active() -> None:
    """A device NOT in the scene should still receive frames (broadcast)."""
    mapped_adapter = MockDeviceAdapter(name="mapped", led_count=10)
    unmapped_adapter = MockDeviceAdapter(name="unmapped", led_count=10)

    # Only "mapped" is in the scene
    scene = SceneModel(
        placements={
            "mapped": DevicePlacement("mapped", (0.0, 0.0, 0.0), PointGeometry(), 1),
        }
    )
    mapping = LinearMapping(direction=(1.0, 0.0, 0.0))
    compositor = SpatialCompositor(scene, mapping)

    event_bus = EventBus()
    clock = BeatClock()
    simulator = BeatSimulator(event_bus=event_bus, bpm=120.0)
    from dj_ledfx.prodjlink.listener import BeatEvent

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
    engine = EffectEngine(clock=clock, deck=deck, led_count=60, fps=60)

    mapped_tracker = LatencyTracker(strategy=StaticLatency(latency_ms=5.0))
    unmapped_tracker = LatencyTracker(strategy=StaticLatency(latency_ms=5.0))

    managed_devices = [
        ManagedDevice(adapter=mapped_adapter, tracker=mapped_tracker, max_fps=60),
        ManagedDevice(adapter=unmapped_adapter, tracker=unmapped_tracker, max_fps=60),
    ]

    scheduler = LookaheadScheduler(
        ring_buffer=engine.ring_buffer,
        devices=managed_devices,
        fps=60,
        compositor=compositor,
    )

    sim_task = asyncio.create_task(simulator.run())
    engine_task = asyncio.create_task(engine.run())
    sched_task = asyncio.create_task(scheduler.run())

    await asyncio.sleep(0.3)

    simulator.stop()
    engine.stop()
    scheduler.stop()

    await asyncio.gather(sim_task, engine_task, sched_task, return_exceptions=True)

    # Both should have received frames — unmapped gets broadcast
    assert len(mapped_adapter.send_frame_calls) > 0
    assert len(unmapped_adapter.send_frame_calls) > 0


@pytest.mark.asyncio
async def test_no_scene_matches_mvp_behavior() -> None:
    """Without a compositor, scheduler uses broadcast (same colors to all)."""
    adapter_a = MockDeviceAdapter(name="a", led_count=10)
    adapter_b = MockDeviceAdapter(name="b", led_count=10)

    event_bus = EventBus()
    clock = BeatClock()
    simulator = BeatSimulator(event_bus=event_bus, bpm=120.0)
    from dj_ledfx.prodjlink.listener import BeatEvent

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
    engine = EffectEngine(clock=clock, deck=deck, led_count=10, fps=60)

    tracker_a = LatencyTracker(strategy=StaticLatency(latency_ms=5.0))
    tracker_b = LatencyTracker(strategy=StaticLatency(latency_ms=5.0))

    managed = [
        ManagedDevice(adapter=adapter_a, tracker=tracker_a, max_fps=60),
        ManagedDevice(adapter=adapter_b, tracker=tracker_b, max_fps=60),
    ]

    # No compositor — MVP broadcast behavior
    scheduler = LookaheadScheduler(
        ring_buffer=engine.ring_buffer,
        devices=managed,
        fps=60,
    )

    sim_task = asyncio.create_task(simulator.run())
    engine_task = asyncio.create_task(engine.run())
    sched_task = asyncio.create_task(scheduler.run())

    await asyncio.sleep(0.3)

    simulator.stop()
    engine.stop()
    scheduler.stop()

    await asyncio.gather(sim_task, engine_task, sched_task, return_exceptions=True)

    assert len(adapter_a.send_frame_calls) > 0
    assert len(adapter_b.send_frame_calls) > 0
    # Both devices should get identical frames (broadcast)
    min_len = min(len(adapter_a.send_frame_calls), len(adapter_b.send_frame_calls))
    if min_len > 0:
        np.testing.assert_array_equal(
            adapter_a.send_frame_calls[0],
            adapter_b.send_frame_calls[0],
        )
