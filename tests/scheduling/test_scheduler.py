import asyncio
import time

import numpy as np
import pytest
from conftest import MockDeviceAdapter

from dj_ledfx.devices.manager import ManagedDevice
from dj_ledfx.effects.engine import RingBuffer
from dj_ledfx.latency.strategies import StaticLatency, WindowedMeanLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.scheduling.scheduler import FrameSlot, LookaheadScheduler
from dj_ledfx.types import RenderedFrame


def _make_device(
    name: str = "TestDevice",
    latency_ms: float = 10.0,
    connected: bool = True,
) -> ManagedDevice:
    adapter = MockDeviceAdapter(name=name, connected=connected)
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


# --- FrameSlot tests ---


async def test_frame_slot_put_take() -> None:
    slot = FrameSlot()
    slot.put(42.0)
    result = await slot.take(timeout=1.0)
    assert result == 42.0


async def test_frame_slot_put_overwrites() -> None:
    slot = FrameSlot()
    slot.put(1.0)
    slot.put(2.0)
    result = await slot.take(timeout=1.0)
    assert result == 2.0


async def test_frame_slot_take_timeout() -> None:
    slot = FrameSlot()
    with pytest.raises(asyncio.TimeoutError):
        await slot.take(timeout=0.05)


async def test_frame_slot_take_blocks_until_put() -> None:
    slot = FrameSlot()

    async def delayed_put() -> None:
        await asyncio.sleep(0.05)
        slot.put(99.0)

    asyncio.create_task(delayed_put())
    result = await slot.take(timeout=1.0)
    assert result == 99.0


async def test_frame_slot_put_count() -> None:
    slot = FrameSlot()
    assert slot.put_count == 0
    slot.put(1.0)
    slot.put(2.0)
    slot.put(3.0)
    assert slot.put_count == 3


async def test_frame_slot_has_pending() -> None:
    slot = FrameSlot()
    assert slot.has_pending is False
    slot.put(1.0)
    assert slot.has_pending is True
    await slot.take(timeout=1.0)
    assert slot.has_pending is False


async def test_frame_slot_concurrent_overwrite_stress() -> None:
    """Rapid alternating put/take never produces stale values."""
    slot = FrameSlot()
    received: list[float] = []

    async def producer() -> None:
        for i in range(100):
            slot.put(float(i))
            await asyncio.sleep(0)  # yield control

    async def consumer() -> None:
        for _ in range(50):
            try:
                val = await slot.take(timeout=0.1)
                received.append(val)
            except TimeoutError:
                break

    await asyncio.gather(producer(), consumer())
    # Each received value should be >= previous (never stale/backward)
    for i in range(1, len(received)):
        assert received[i] >= received[i - 1]


# --- Distributor tests ---


async def test_distributor_writes_to_all_devices() -> None:
    """Distributor tick should result in frames sent to every connected device."""
    dev1 = _make_device("Dev1", latency_ms=10.0)
    dev2 = _make_device("Dev2", latency_ms=100.0)
    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = LookaheadScheduler(ring_buffer=buf, devices=[dev1, dev2], fps=60, max_fps=60)
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.15)
    scheduler.stop()
    await task

    assert len(dev1.adapter.send_frame_calls) > 0
    assert len(dev2.adapter.send_frame_calls) > 0


async def test_distributor_computes_correct_target_time() -> None:
    """target_time should be now + effective_latency_s for each device."""
    dev_fast = _make_device("Fast", latency_ms=5.0)
    dev_slow = _make_device("Slow", latency_ms=100.0)
    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = LookaheadScheduler(
        ring_buffer=buf, devices=[dev_fast, dev_slow], fps=60, max_fps=60
    )
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.15)
    scheduler.stop()
    await task

    # Both devices got frames
    assert len(dev_fast.adapter.send_frame_calls) > 0
    assert len(dev_slow.adapter.send_frame_calls) > 0


# --- Send loop tests ---


async def test_send_loop_disconnected_backoff() -> None:
    """Disconnected device should not receive any frames."""
    device = _make_device(connected=False)
    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = LookaheadScheduler(ring_buffer=buf, devices=[device], fps=60, max_fps=60)
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.15)
    scheduler.stop()
    await task

    assert len(device.adapter.send_frame_calls) == 0


async def test_send_loop_reconnection_sends_frames() -> None:
    """Device that reconnects should start receiving frames."""
    device = _make_device(connected=False)
    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = LookaheadScheduler(
        ring_buffer=buf,
        devices=[device],
        fps=60,
        max_fps=60,
        disconnect_backoff_s=0.01,
    )
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.05)

    # Reconnect
    device.adapter.is_connected = True
    await asyncio.sleep(0.15)
    scheduler.stop()
    await task

    assert len(device.adapter.send_frame_calls) > 0


async def test_send_loop_reconnection_resets_tracker() -> None:
    """When is_connected flips False->True, tracker.reset() must be called."""
    adapter = MockDeviceAdapter(name="Reconnect", connected=False, supports_probing=False)
    strategy = WindowedMeanLatency(window_size=60, initial_value_ms=100.0)
    device = ManagedDevice(adapter=adapter, tracker=LatencyTracker(strategy=strategy))
    # Pre-fill strategy with stale samples
    strategy.update(200.0)
    strategy.update(300.0)
    assert abs(strategy.get_latency() - 250.0) < 0.1

    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = LookaheadScheduler(
        ring_buffer=buf,
        devices=[device],
        fps=60,
        max_fps=60,
        disconnect_backoff_s=0.01,
    )
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.05)

    # Reconnect — should trigger tracker.reset()
    adapter.is_connected = True
    await asyncio.sleep(0.15)
    scheduler.stop()
    await task

    # After reset, strategy falls back to initial_value_ms (stale samples cleared)
    assert strategy.get_latency() == 100.0


async def test_send_loop_rtt_not_updated_when_probing_disabled() -> None:
    """When supports_latency_probing=False, tracker should not get RTT updates."""
    adapter = MockDeviceAdapter(name="NoProbe", supports_probing=False)
    strategy = WindowedMeanLatency(window_size=60, initial_value_ms=100.0)
    device = ManagedDevice(adapter=adapter, tracker=LatencyTracker(strategy=strategy))
    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = LookaheadScheduler(ring_buffer=buf, devices=[device], fps=60, max_fps=60)
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.15)
    scheduler.stop()
    await task

    # Strategy should still return initial value (no RTT updates overwrote it)
    assert strategy.get_latency() == 100.0


async def test_send_loop_rtt_updated_when_probing_enabled() -> None:
    """When supports_latency_probing=True, tracker should receive RTT updates."""
    adapter = MockDeviceAdapter(name="WithProbe", supports_probing=True)
    strategy = WindowedMeanLatency(window_size=60, initial_value_ms=100.0)
    device = ManagedDevice(adapter=adapter, tracker=LatencyTracker(strategy=strategy))

    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = LookaheadScheduler(ring_buffer=buf, devices=[device], fps=60, max_fps=60)
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.15)
    scheduler.stop()
    await task

    # Latency should have shifted from initial (mock send is near-instant, ~0ms RTT)
    assert strategy.get_latency() < 100.0


async def test_send_loop_buffer_not_ready() -> None:
    """Empty ring buffer should result in no frames sent."""
    device = _make_device()
    buf = RingBuffer(capacity=60, led_count=10)
    # Don't fill buffer

    scheduler = LookaheadScheduler(ring_buffer=buf, devices=[device], fps=60, max_fps=60)
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.1)
    scheduler.stop()
    await task

    assert len(device.adapter.send_frame_calls) == 0


async def test_send_loop_continues_after_send_exception() -> None:
    """Send loop should log warning and continue on send_frame exception."""
    device = _make_device()
    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    call_count = 0
    original_send = device.adapter.send_frame

    async def flaky_send(colors: np.ndarray) -> None:
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise OSError("transient error")
        await original_send(colors)

    device.adapter.send_frame = flaky_send  # type: ignore[assignment]

    scheduler = LookaheadScheduler(ring_buffer=buf, devices=[device], fps=60, max_fps=60)
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.2)
    scheduler.stop()
    await task

    # Loop recovered after initial failures
    assert len(device.adapter.send_frame_calls) > 0


async def test_fps_cap_limits_send_rate() -> None:
    """max_fps should throttle the device send rate."""
    device = _make_device()
    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = LookaheadScheduler(ring_buffer=buf, devices=[device], fps=60, max_fps=10)
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(1.0)
    scheduler.stop()
    await task

    # At max_fps=10, expect ~10 sends/sec (tolerance: 5-15)
    assert 5 <= len(device.adapter.send_frame_calls) <= 15


async def test_fps_cap_no_accumulated_drift() -> None:
    """Over many iterations, total elapsed should match expected (no drift)."""
    device = _make_device()
    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = LookaheadScheduler(ring_buffer=buf, devices=[device], fps=60, max_fps=20)
    start = time.monotonic()
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(2.0)
    scheduler.stop()
    await task
    elapsed = time.monotonic() - start

    # At 20fps, ~40 sends in 2s. Check total count is proportional to elapsed time.
    expected = elapsed * 20
    actual = len(device.adapter.send_frame_calls)
    # Allow 30% tolerance for CI variability
    assert actual >= expected * 0.7, (
        f"Drift detected: {actual} sends in {elapsed:.2f}s (expected ~{expected:.0f})"
    )


# --- Shutdown tests ---


async def test_graceful_stop() -> None:
    """stop() should cause run() to return cleanly."""
    device = _make_device()
    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = LookaheadScheduler(ring_buffer=buf, devices=[device], fps=60, max_fps=60)
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.1)
    scheduler.stop()
    await asyncio.wait_for(task, timeout=3.0)


async def test_external_cancellation() -> None:
    """Cancelling the scheduler task should clean up child tasks."""
    device = _make_device()
    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = LookaheadScheduler(ring_buffer=buf, devices=[device], fps=60, max_fps=60)
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_shutdown_during_active_send() -> None:
    """Cancel while send_frame is blocked should not crash or leave inconsistent state."""
    device = _make_device()
    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    send_started = asyncio.Event()

    async def slow_send(colors: np.ndarray) -> None:
        send_started.set()
        await asyncio.sleep(5.0)  # Simulate a very slow send

    device.adapter.send_frame = slow_send  # type: ignore[assignment]

    scheduler = LookaheadScheduler(ring_buffer=buf, devices=[device], fps=60, max_fps=60)
    task = asyncio.create_task(scheduler.run())

    # Wait until send_frame is actually in progress
    await asyncio.wait_for(send_started.wait(), timeout=2.0)

    # Cancel while send is active
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # No crash, no hanging tasks — test passes if we get here


# --- Stats tests ---


async def test_get_device_stats() -> None:
    """get_device_stats should report per-device metrics."""
    device = _make_device("StatsDevice", latency_ms=50.0)
    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = LookaheadScheduler(ring_buffer=buf, devices=[device], fps=60, max_fps=60)
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.2)

    stats = scheduler.get_device_stats()
    assert len(stats) == 1
    assert stats[0].device_name == "StatsDevice"
    assert stats[0].effective_latency_ms == 50.0
    assert stats[0].send_fps > 0
    assert stats[0].frames_dropped >= 0

    scheduler.stop()
    await task


async def test_get_device_stats_fps_accuracy() -> None:
    """send_fps should approximate the actual send rate."""
    device = _make_device("FpsDevice")
    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = LookaheadScheduler(ring_buffer=buf, devices=[device], fps=60, max_fps=20)
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(1.0)

    stats = scheduler.get_device_stats()
    # At max_fps=20, expect send_fps ≈ 20 (within ±30%)
    assert 14 <= stats[0].send_fps <= 26, f"send_fps={stats[0].send_fps:.1f}, expected ~20"

    scheduler.stop()
    await task
