import asyncio
import time
from unittest.mock import AsyncMock, PropertyMock

import numpy as np

from dj_ledfx.devices.manager import ManagedDevice
from dj_ledfx.effects.engine import RingBuffer
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.scheduling.scheduler import LookaheadScheduler
from dj_ledfx.types import DeviceInfo, RenderedFrame


def _make_device(latency_ms: float = 10.0) -> ManagedDevice:
    adapter = AsyncMock()
    type(adapter).is_connected = PropertyMock(return_value=True)
    type(adapter).led_count = PropertyMock(return_value=10)
    type(adapter).device_info = PropertyMock(
        return_value=DeviceInfo(
            name="TestDevice", device_type="mock", led_count=10, address="mock"
        )
    )
    tracker = LatencyTracker(strategy=StaticLatency(latency_ms))
    return ManagedDevice(adapter=adapter, tracker=tracker)


def _fill_buffer(buf: RingBuffer, base_time: float, count: int = 60) -> None:
    for i in range(count):
        frame = RenderedFrame(
            colors=np.full((10, 3), i % 256, dtype=np.uint8),
            target_time=base_time + i * (1.0 / 60.0),
            beat_phase=0.0,
            bar_phase=0.0,
        )
        buf.write(frame)


async def test_scheduler_dispatches_frame() -> None:
    device = _make_device(latency_ms=10.0)
    buf = RingBuffer(capacity=60, led_count=10)
    now = time.monotonic()
    _fill_buffer(buf, now, 60)

    scheduler = LookaheadScheduler(
        ring_buffer=buf,
        devices=[device],
        fps=60,
    )

    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.1)
    scheduler.stop()
    await task

    assert device.adapter.send_frame.call_count >= 1


async def test_scheduler_picks_correct_frame_for_latency() -> None:
    buf = RingBuffer(capacity=60, led_count=10)
    now = time.monotonic()
    _fill_buffer(buf, now, 60)

    frame = buf.find_nearest(now + 0.5)
    assert frame is not None
    assert abs(frame.target_time - (now + 0.5)) < 0.02
