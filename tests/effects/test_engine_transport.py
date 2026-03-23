from __future__ import annotations

import asyncio
import time

import numpy as np
import pytest

from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.effects.deck import EffectDeck
from dj_ledfx.effects.engine import EffectEngine, RingBuffer
from dj_ledfx.events import EventBus, TransportStateChangedEvent
from dj_ledfx.transport import TransportState
from dj_ledfx.types import RenderedFrame


def test_ring_buffer_clear() -> None:
    buf = RingBuffer(capacity=10, led_count=3)
    frame = RenderedFrame(
        colors=np.zeros((3, 3), dtype=np.uint8),
        target_time=time.monotonic(),
        beat_phase=0.0,
        bar_phase=0.0,
    )
    buf.write(frame)
    assert buf.count == 1
    buf.clear()
    assert buf.count == 0
    assert buf.find_nearest(time.monotonic()) is None


@pytest.fixture
def clock() -> BeatClock:
    c = BeatClock()
    c.on_beat(
        bpm=120.0,
        beat_number=1,
        next_beat_ms=500,
        timestamp=time.monotonic(),
        pitch_percent=0.0,
        device_number=1,
        device_name="test",
    )
    return c


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def engine(clock: BeatClock, event_bus: EventBus) -> EffectEngine:
    from dj_ledfx.effects.registry import get_effect_classes

    effect_classes = get_effect_classes()
    effect = list(effect_classes.values())[0]()
    deck = EffectDeck(effect)
    return EffectEngine(clock, deck, led_count=10, fps=60, event_bus=event_bus)


def test_engine_starts_stopped(engine: EffectEngine) -> None:
    assert engine.transport_state == TransportState.STOPPED


def test_engine_set_transport_state(engine: EffectEngine) -> None:
    engine.set_transport_state(TransportState.PLAYING)
    assert engine.transport_state == TransportState.PLAYING


def test_engine_set_transport_emits_event(
    engine: EffectEngine, event_bus: EventBus
) -> None:
    received: list[TransportStateChangedEvent] = []
    event_bus.subscribe(TransportStateChangedEvent, received.append)
    engine.set_transport_state(TransportState.PLAYING)
    assert len(received) == 1
    assert received[0].old_state == TransportState.STOPPED
    assert received[0].new_state == TransportState.PLAYING


def test_engine_no_event_on_same_state(
    engine: EffectEngine, event_bus: EventBus
) -> None:
    engine.set_transport_state(TransportState.PLAYING)
    received: list[TransportStateChangedEvent] = []
    event_bus.subscribe(TransportStateChangedEvent, received.append)
    engine.set_transport_state(TransportState.PLAYING)
    assert len(received) == 0


@pytest.mark.asyncio
async def test_engine_run_blocks_when_stopped(engine: EffectEngine) -> None:
    task = asyncio.create_task(engine.run())
    await asyncio.sleep(0.05)
    assert engine.ring_buffer.count == 0
    engine.stop()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_engine_run_renders_when_playing(engine: EffectEngine) -> None:
    engine.set_transport_state(TransportState.PLAYING)
    task = asyncio.create_task(engine.run())
    await asyncio.sleep(0.05)
    assert engine.ring_buffer.count > 0
    engine.stop()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_engine_clears_buffer_on_stop(engine: EffectEngine) -> None:
    engine.set_transport_state(TransportState.PLAYING)
    task = asyncio.create_task(engine.run())
    await asyncio.sleep(0.05)
    assert engine.ring_buffer.count > 0
    engine.set_transport_state(TransportState.STOPPED)
    assert engine.ring_buffer.count == 0
    engine.stop()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
