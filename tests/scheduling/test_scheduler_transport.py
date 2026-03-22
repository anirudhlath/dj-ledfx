"""Tests for scheduler transport gating (STOPPED / PLAYING / SIMULATING)."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from dj_ledfx.effects.engine import RingBuffer
from dj_ledfx.events import EventBus, TransportStateChangedEvent
from dj_ledfx.scheduling.scheduler import LookaheadScheduler
from dj_ledfx.transport import TransportState
from dj_ledfx.types import DeviceInfo, RenderedFrame


# --- helpers ---


def _mock_managed(name: str = "TestDev", stable_id: str = "test:aa") -> MagicMock:
    """Create a MagicMock that quacks like ManagedDevice."""
    managed = MagicMock()
    managed.adapter = AsyncMock()
    managed.adapter.device_info = DeviceInfo(
        name=name,
        device_type="test",
        led_count=3,
        address="",
        stable_id=stable_id,
    )
    managed.adapter.is_connected = True
    managed.adapter.send_frame = AsyncMock()
    managed.adapter.supports_latency_probing = False
    managed.tracker = MagicMock()
    managed.tracker.effective_latency_s = 0.01
    managed.tracker.effective_latency_ms = 10.0
    managed.max_fps = 60
    return managed


def _fill_buffer(buf: RingBuffer, count: int = 10) -> None:
    base_time = time.monotonic()
    for i in range(count):
        frame = RenderedFrame(
            colors=np.full((3, 3), i % 256, dtype=np.uint8),
            target_time=base_time + i * (1.0 / 60.0),
            beat_phase=0.0,
            bar_phase=0.0,
        )
        buf.write(frame)


# --- fixtures ---


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def ring_buffer() -> RingBuffer:
    buf = RingBuffer(capacity=60, led_count=3)
    _fill_buffer(buf, count=10)
    return buf


# --- tests ---


def test_scheduler_starts_stopped(event_bus: EventBus, ring_buffer: RingBuffer) -> None:
    managed = _mock_managed()
    scheduler = LookaheadScheduler(
        ring_buffer=ring_buffer, devices=[managed], event_bus=event_bus
    )
    assert scheduler.transport_state is TransportState.STOPPED


def test_scheduler_responds_to_transport_event(
    event_bus: EventBus, ring_buffer: RingBuffer
) -> None:
    managed = _mock_managed()
    scheduler = LookaheadScheduler(
        ring_buffer=ring_buffer, devices=[managed], event_bus=event_bus
    )
    assert scheduler.transport_state is TransportState.STOPPED

    event_bus.emit(
        TransportStateChangedEvent(
            old_state=TransportState.STOPPED, new_state=TransportState.PLAYING
        )
    )
    assert scheduler.transport_state is TransportState.PLAYING

    event_bus.emit(
        TransportStateChangedEvent(
            old_state=TransportState.PLAYING, new_state=TransportState.SIMULATING
        )
    )
    assert scheduler.transport_state is TransportState.SIMULATING

    event_bus.emit(
        TransportStateChangedEvent(
            old_state=TransportState.SIMULATING, new_state=TransportState.STOPPED
        )
    )
    assert scheduler.transport_state is TransportState.STOPPED


@pytest.mark.asyncio
async def test_scheduler_blocks_when_stopped(
    event_bus: EventBus, ring_buffer: RingBuffer
) -> None:
    managed = _mock_managed()
    scheduler = LookaheadScheduler(
        ring_buffer=ring_buffer, devices=[managed], event_bus=event_bus
    )
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.05)

    # Still STOPPED — no send_frame calls
    managed.adapter.send_frame.assert_not_called()

    scheduler.stop()
    await asyncio.wait_for(task, timeout=2.0)


@pytest.mark.asyncio
async def test_scheduler_sends_when_playing(
    event_bus: EventBus, ring_buffer: RingBuffer
) -> None:
    managed = _mock_managed()
    scheduler = LookaheadScheduler(
        ring_buffer=ring_buffer, devices=[managed], event_bus=event_bus
    )

    # Transition to PLAYING
    event_bus.emit(
        TransportStateChangedEvent(
            old_state=TransportState.STOPPED, new_state=TransportState.PLAYING
        )
    )

    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.1)
    scheduler.stop()
    await asyncio.wait_for(task, timeout=2.0)

    assert managed.adapter.send_frame.call_count > 0


@pytest.mark.asyncio
async def test_scheduler_skips_send_when_simulating(
    event_bus: EventBus, ring_buffer: RingBuffer
) -> None:
    managed = _mock_managed()
    scheduler = LookaheadScheduler(
        ring_buffer=ring_buffer, devices=[managed], event_bus=event_bus
    )

    # Transition to SIMULATING
    event_bus.emit(
        TransportStateChangedEvent(
            old_state=TransportState.STOPPED, new_state=TransportState.SIMULATING
        )
    )

    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.1)
    scheduler.stop()
    await asyncio.wait_for(task, timeout=2.0)

    # send_frame should NOT have been called
    managed.adapter.send_frame.assert_not_called()

    # But frame_snapshots should be populated
    assert len(scheduler.frame_snapshots) > 0
