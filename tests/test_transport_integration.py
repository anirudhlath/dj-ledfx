"""Full transport lifecycle integration test.

Exercises the STOPPED → PLAYING → SIMULATING → STOPPED state machine with a real
EffectEngine + LookaheadScheduler wired together via an EventBus.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.devices.manager import ManagedDevice
from dj_ledfx.effects.deck import EffectDeck
from dj_ledfx.effects.engine import EffectEngine
from dj_ledfx.events import EventBus, TransportStateChangedEvent
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.scheduling.scheduler import LookaheadScheduler
from dj_ledfx.transport import TransportState
from conftest import MockDeviceAdapter


def _make_clock() -> BeatClock:
    clock = BeatClock()
    clock.on_beat(
        bpm=120.0,
        beat_number=1,
        next_beat_ms=500,
        timestamp=time.monotonic(),
        pitch_percent=0.0,
        device_number=1,
        device_name="test",
    )
    return clock


@pytest.mark.asyncio
async def test_transport_lifecycle() -> None:
    """STOPPED → PLAYING → SIMULATING → STOPPED lifecycle integration test."""
    # --- Setup ---
    event_bus = EventBus()
    clock = _make_clock()

    from dj_ledfx.effects.registry import get_effect_classes

    effect_classes = get_effect_classes()
    effect = list(effect_classes.values())[0]()
    deck = EffectDeck(effect)

    engine = EffectEngine(
        clock=clock,
        deck=deck,
        led_count=10,
        fps=60,
        max_lookahead_s=0.5,
        event_bus=event_bus,
    )

    adapter = MockDeviceAdapter(name="IntegrationLED", led_count=10)
    tracker = LatencyTracker(strategy=StaticLatency(5.0))
    managed = ManagedDevice(adapter=adapter, tracker=tracker, max_fps=60)

    scheduler = LookaheadScheduler(
        ring_buffer=engine.ring_buffer,
        devices=[managed],
        fps=60,
        event_bus=event_bus,
    )

    # --- Start tasks ---
    engine_task = asyncio.create_task(engine.run())
    sched_task = asyncio.create_task(scheduler.run())

    # Give the event loop a moment to kick off the tasks
    await asyncio.sleep(0.02)

    # --- Assert STOPPED: no frames rendered, no send_frame calls ---
    assert engine.transport_state is TransportState.STOPPED
    assert engine.ring_buffer.count == 0
    assert len(adapter.send_frame_calls) == 0

    # --- Transition to PLAYING ---
    engine.set_transport_state(TransportState.PLAYING)
    # event_bus carries the event to both engine and scheduler
    await asyncio.sleep(0.1)

    assert engine.transport_state is TransportState.PLAYING
    assert scheduler.transport_state is TransportState.PLAYING
    assert engine.ring_buffer.count > 0, "Engine should be rendering frames"
    send_count_after_playing = len(adapter.send_frame_calls)
    assert send_count_after_playing > 0, "Scheduler should be sending frames"

    # --- Transition to SIMULATING ---
    engine.set_transport_state(TransportState.SIMULATING)
    await asyncio.sleep(0.02)

    assert engine.transport_state is TransportState.SIMULATING
    assert scheduler.transport_state is TransportState.SIMULATING

    # Record send count at transition boundary, then wait and check it did NOT grow
    count_at_sim_start = len(adapter.send_frame_calls)
    await asyncio.sleep(0.1)
    count_after_sim = len(adapter.send_frame_calls)
    assert count_after_sim == count_at_sim_start, (
        "send_frame should not be called while SIMULATING"
    )

    # --- Transition to STOPPED ---
    engine.set_transport_state(TransportState.STOPPED)
    await asyncio.sleep(0.02)

    assert engine.transport_state is TransportState.STOPPED
    assert scheduler.transport_state is TransportState.STOPPED
    assert engine.ring_buffer.count == 0, "Ring buffer should be cleared on STOPPED"

    # --- Cleanup ---
    # stop() sets _running=False but doesn't unblock resume_event.wait().
    # Cancel the tasks to unblock them, then gather to let finally blocks run.
    engine.stop()
    scheduler.stop()
    engine_task.cancel()
    sched_task.cancel()
    await asyncio.gather(engine_task, sched_task, return_exceptions=True)
