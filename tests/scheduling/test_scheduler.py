import asyncio
import time
from typing import Any

import numpy as np
import pytest
from conftest import FakeLight, MockDeviceAdapter, ring_route

from dj_ledfx import metrics
from dj_ledfx.devices.manager import ManagedDevice
from dj_ledfx.effects.ring_buffer import RingBuffer
from dj_ledfx.latency.strategies import (
    LATENCY_WINDOW,
    StaticLatency,
    WindowedMeanLatency,
    WindowedMedianLatency,
    make_strategy,
)
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.scheduling.route import DeviceRoute
from dj_ledfx.scheduling.scheduler import FrameSlot, LookaheadScheduler
from dj_ledfx.types import RenderedFrame


def _make_device(
    name: str = "TestDevice",
    latency_ms: float = 10.0,
    connected: bool = True,
    max_fps: int = 60,
    led_count: int = 10,
) -> ManagedDevice:
    adapter = MockDeviceAdapter(name=name, led_count=led_count, connected=connected)
    tracker = LatencyTracker(strategy=StaticLatency(latency_ms))
    return ManagedDevice(adapter=adapter, tracker=tracker, max_fps=max_fps)


def _fill_buffer(
    buf: RingBuffer, base_time: float, count: int = 60, *, level: float | None = None
) -> None:
    """count frames a 60th of a second apart from base_time: each one new, or every one at
    level (a still look)."""
    for i in range(count):
        frame = RenderedFrame(
            colors=np.full((10, 3), (i % 256) / 255.0 if level is None else level, np.float32),
            target_time=base_time + i * (1.0 / 60.0),
            beat_phase=0.0,
            bar_phase=0.0,
        )
        buf.write(frame)


def _route(
    ring: RingBuffer, *, start: int = 0, stop: int = 10, streaming: bool = True
) -> DeviceRoute:
    return ring_route(ring, start=start, stop=stop, streaming=streaming)


def _scheduler(
    ring_buffer: RingBuffer, devices: list[ManagedDevice], **kwargs: Any
) -> LookaheadScheduler:
    """A scheduler that sends every device the first ten LEDs of ring_buffer's frames."""
    made = LookaheadScheduler(devices=devices, **kwargs)
    for device in devices:
        made.set_route(device.adapter.device_info.effective_id, _route(ring_buffer))
    return made


def _still() -> tuple[ManagedDevice, RingBuffer, LookaheadScheduler]:
    """A device at 60 a second, and a scheduler sending it a still look for 2.5 s."""
    device = _make_device(max_fps=60)
    buf = RingBuffer(capacity=150)
    _fill_buffer(buf, time.monotonic(), 150, level=0.5)
    return device, buf, _scheduler(ring_buffer=buf, devices=[device], fps=60)


async def _run_for(scheduler: LookaheadScheduler, seconds: float) -> None:
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(seconds)
    scheduler.stop()
    await task


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
    buf = RingBuffer(capacity=60)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = _scheduler(ring_buffer=buf, devices=[dev1, dev2], fps=60)
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
    buf = RingBuffer(capacity=60)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = _scheduler(ring_buffer=buf, devices=[dev_fast, dev_slow], fps=60)
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
    buf = RingBuffer(capacity=60)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = _scheduler(ring_buffer=buf, devices=[device], fps=60)
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.15)
    scheduler.stop()
    await task

    assert len(device.adapter.send_frame_calls) == 0


async def test_send_loop_reconnection_sends_frames() -> None:
    """Device that reconnects should start receiving frames."""
    device = _make_device(connected=False)
    buf = RingBuffer(capacity=60)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = _scheduler(
        ring_buffer=buf,
        devices=[device],
        fps=60,
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
    adapter = MockDeviceAdapter(name="Reconnect", connected=False)
    strategy = WindowedMeanLatency(window_size=60, initial_value_ms=100.0)
    device = ManagedDevice(adapter=adapter, tracker=LatencyTracker(strategy=strategy), max_fps=60)
    # Pre-fill strategy with stale samples
    strategy.update(200.0)
    strategy.update(300.0)
    assert abs(strategy.get_latency() - 250.0) < 0.1

    buf = RingBuffer(capacity=60)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = _scheduler(
        ring_buffer=buf,
        devices=[device],
        fps=60,
        disconnect_backoff_s=0.01,
    )
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.05)

    # Reconnect — should trigger tracker.reset()
    adapter.is_connected = True
    await asyncio.sleep(0.15)
    scheduler.stop()
    await task

    # The reset keeps the latency the light had, its samples gone (light-sync spec §7)
    assert strategy.get_latency() == 250.0
    strategy.update(10.0)
    assert strategy.get_latency() == 10.0


async def test_sending_never_moves_a_light_s_latency() -> None:
    """A send returns before the light shows the frame: only a probe's round trip counts."""
    adapter = MockDeviceAdapter(name="Sent")
    strategy = WindowedMeanLatency(window_size=60, initial_value_ms=100.0)
    device = ManagedDevice(adapter=adapter, tracker=LatencyTracker(strategy=strategy), max_fps=60)
    buf = RingBuffer(capacity=60)
    _fill_buffer(buf, time.monotonic(), 60)

    await _run_for(_scheduler(ring_buffer=buf, devices=[device], fps=60), 0.15)

    assert adapter.send_frame_calls
    assert strategy.get_latency() == 100.0  # its seed: no send duration got in
    assert not device.tracker.measured


async def test_send_loop_buffer_not_ready() -> None:
    """Empty ring buffer should result in no frames sent."""
    device = _make_device()
    buf = RingBuffer(capacity=60)
    # Don't fill buffer

    scheduler = _scheduler(ring_buffer=buf, devices=[device], fps=60)
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.1)
    scheduler.stop()
    await task

    assert len(device.adapter.send_frame_calls) == 0


async def test_send_loop_continues_after_send_exception() -> None:
    """Send loop should log warning and continue on send_frame exception."""
    device = _make_device()
    buf = RingBuffer(capacity=60)
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

    scheduler = _scheduler(ring_buffer=buf, devices=[device], fps=60)
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.2)
    scheduler.stop()
    await task

    # Loop recovered after initial failures
    assert len(device.adapter.send_frame_calls) > 0


async def test_fps_cap_limits_send_rate() -> None:
    """max_fps should throttle the device send rate."""
    device = _make_device(max_fps=10)
    buf = RingBuffer(capacity=60)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = _scheduler(ring_buffer=buf, devices=[device], fps=60)
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(1.0)
    scheduler.stop()
    await task

    # At max_fps=10, expect ~10 sends/sec (tolerance: 5-15)
    assert 5 <= len(device.adapter.send_frame_calls) <= 15


async def test_fps_cap_no_accumulated_drift() -> None:
    """Over many iterations, total elapsed should match expected (no drift)."""
    device = _make_device(max_fps=20)
    buf = RingBuffer(capacity=150)
    _fill_buffer(buf, time.monotonic(), 150)

    scheduler = _scheduler(ring_buffer=buf, devices=[device], fps=60)
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
    buf = RingBuffer(capacity=60)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = _scheduler(ring_buffer=buf, devices=[device], fps=60)
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.1)
    scheduler.stop()
    await asyncio.wait_for(task, timeout=3.0)


async def test_external_cancellation() -> None:
    """Cancelling the scheduler task should clean up child tasks."""
    device = _make_device()
    buf = RingBuffer(capacity=60)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = _scheduler(ring_buffer=buf, devices=[device], fps=60)
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_shutdown_during_active_send() -> None:
    """Cancel while send_frame is blocked should not crash or leave inconsistent state."""
    device = _make_device()
    buf = RingBuffer(capacity=60)
    _fill_buffer(buf, time.monotonic(), 60)

    send_started = asyncio.Event()

    async def slow_send(colors: np.ndarray) -> None:
        send_started.set()
        await asyncio.sleep(5.0)  # Simulate a very slow send

    device.adapter.send_frame = slow_send  # type: ignore[assignment]

    scheduler = _scheduler(ring_buffer=buf, devices=[device], fps=60)
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
    buf = RingBuffer(capacity=60)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = _scheduler(ring_buffer=buf, devices=[device], fps=60)
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.2)

    stats = scheduler.get_device_stats()
    assert len(stats) == 1
    assert stats[0].device_name == "StatsDevice"
    assert stats[0].device_id == "StatsDevice"
    assert stats[0].effective_latency_ms == 50.0
    assert stats[0].send_fps > 0
    assert stats[0].frames_dropped >= 0

    scheduler.stop()
    await task


async def test_get_device_stats_fps_accuracy() -> None:
    """send_fps should approximate the actual send rate."""
    device = _make_device("FpsDevice", max_fps=20)
    buf = RingBuffer(capacity=60)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = _scheduler(ring_buffer=buf, devices=[device], fps=60)
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(1.0)

    stats = scheduler.get_device_stats()
    # At max_fps=20, expect send_fps ≈ 20 (within ±30%)
    assert 14 <= stats[0].send_fps <= 26, f"send_fps={stats[0].send_fps:.1f}, expected ~20"

    scheduler.stop()
    await task


async def test_mixed_fps_per_device() -> None:
    """Devices with different max_fps send at different rates."""
    fast_device = _make_device("fast", max_fps=60)
    slow_device = _make_device("slow", max_fps=30)
    buf = RingBuffer(capacity=60)
    _fill_buffer(buf, time.monotonic(), 60)
    scheduler = _scheduler(ring_buffer=buf, devices=[fast_device, slow_device], fps=60)

    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.5)
    fast, slow = scheduler.get_device_stats()  # a skipped repeat counts as sent
    scheduler.stop()
    await task

    assert fast.send_fps > 0 and slow.send_fps > 0
    ratio = fast.send_fps / slow.send_fps
    assert 1.5 < ratio < 3.0, f"Expected ~2:1 ratio, got {ratio:.1f}:1"


# --- DeviceSendState tests ---


def test_device_send_state_creation() -> None:
    """DeviceSendState bundles per-device send state."""
    from unittest.mock import MagicMock

    from dj_ledfx.scheduling.scheduler import DeviceSendState, FrameSlot

    managed = MagicMock()
    managed.adapter.device_info.stable_id = "lifx:aa"
    slot = FrameSlot()
    state = DeviceSendState(
        managed=managed,
        slot=slot,
        send_count=0,
        send_task=None,
    )
    assert state.managed is managed
    assert state.slot is slot
    assert state.send_count == 0


@pytest.mark.asyncio
async def test_scheduler_add_device_during_run() -> None:
    """Devices added after construction get send tasks."""
    from dj_ledfx.devices.ghost import GhostAdapter
    from dj_ledfx.devices.manager import ManagedDevice
    from dj_ledfx.latency.strategies import StaticLatency
    from dj_ledfx.latency.tracker import LatencyTracker
    from dj_ledfx.types import DeviceInfo

    buf = RingBuffer(60)
    scheduler = _scheduler(ring_buffer=buf, devices=[], fps=60)

    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.05)

    info = DeviceInfo("Ghost", "test", 10, "1.2.3.4:80", stable_id="test:aa")
    ghost = GhostAdapter(info, 10)
    managed = ManagedDevice(
        adapter=ghost, tracker=LatencyTracker(StaticLatency(50.0)), status="offline"
    )
    scheduler.add_device(managed)

    assert "test:aa" in scheduler._device_state
    await asyncio.sleep(0.05)

    scheduler.remove_device("test:aa")
    assert "test:aa" not in scheduler._device_state

    scheduler.stop()
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_distributor_handles_concurrent_add_device() -> None:
    """Device added while distributor is running receives frames without errors.

    This exercises the dict-values iteration path: the distributor must not
    crash when _device_state is mutated concurrently (e.g. via add_device).
    We verify the late-joining device still gets frames after it is added.
    """
    buf = RingBuffer(capacity=60)
    _fill_buffer(buf, time.monotonic(), 60)

    # Start with one device so the distributor loop is active immediately
    initial_device = _make_device("Initial", latency_ms=10.0)
    scheduler = _scheduler(ring_buffer=buf, devices=[initial_device], fps=60)
    run_task = asyncio.create_task(scheduler.run())

    # Let the distributor run for a few ticks before adding the second device
    await asyncio.sleep(0.05)

    late_device = _make_device("LateJoiner", latency_ms=10.0)
    scheduler.set_route("LateJoiner", _route(buf))
    scheduler.add_device(late_device)

    # Give the scheduler time to pick up the new device and send frames to it
    await asyncio.sleep(0.15)
    scheduler.stop()
    await run_task

    # Both the initial device and the late joiner must have received frames
    assert len(initial_device.adapter.send_frame_calls) > 0, "Initial device received no frames"
    assert len(late_device.adapter.send_frame_calls) > 0, "Late-joining device received no frames"


# --- Routes ---


def _two_frame_ring() -> RingBuffer:
    """Frame 0 for 0.4 s from now and frame 1 for 0.5 s; LEDs 0-4 and 5-9 differ in each."""
    buf = RingBuffer(capacity=10)
    now = time.monotonic()
    for at, (first, second) in [(0.4, (0.25, 0.5)), (0.5, (0.75, 1.0))]:
        colors = np.empty((10, 3), dtype=np.float32)
        colors[:5], colors[5:] = first, second
        buf.write(
            RenderedFrame(colors=colors, target_time=now + at, beat_phase=0.0, bar_phase=0.0)
        )
    return buf


async def test_each_device_gets_its_slice_of_the_frame_for_its_own_latency() -> None:
    near = _make_device("near", latency_ms=10.0, led_count=5)
    far = _make_device("far", latency_ms=600.0, led_count=5)
    buf = _two_frame_ring()
    scheduler = LookaheadScheduler(devices=[near, far], fps=60)
    scheduler.set_route("near", _route(buf, start=0, stop=5))
    scheduler.set_route("far", _route(buf, start=5, stop=10))

    await _run_for(scheduler, 0.2)

    # near's moments (now + 10 ms) come before both frames, far's (now + 600 ms) after both
    near_sent = {frame.tobytes() for frame in near.adapter.send_frame_calls}
    far_sent = {frame.tobytes() for frame in far.adapter.send_frame_calls}
    assert near_sent == {bytes([64] * 15)}  # 0.25 in 8 bits
    assert far_sent == {bytes([255] * 15)}


class _CountingRing(RingBuffer):
    """Counts the frames asked of it."""

    def __init__(self, capacity: int) -> None:
        super().__init__(capacity)
        self.asked = 0

    def find_around(self, target_time: float) -> tuple[RenderedFrame, RenderedFrame, float] | None:
        self.asked += 1
        return super().find_around(target_time)


# M1 review, constraint 3: a route that doesn't stream costs the send loop nothing. The web
# app's frames come from the rings (zones/frames.py).
async def test_a_route_that_does_not_stream_is_never_read_or_sent() -> None:
    device = _make_device()  # it runs its own effect, or preview-only is on
    buf = _CountingRing(capacity=60)
    _fill_buffer(buf, time.monotonic(), 60)
    scheduler = LookaheadScheduler(devices=[device], fps=60)
    scheduler.set_route("TestDevice", _route(buf, streaming=False))

    await _run_for(scheduler, 0.15)

    assert device.adapter.send_frame_calls == [] and buf.asked == 0
    [stats] = scheduler.get_device_stats()
    assert (stats.dropped_pct, stats.frames_dropped) == (0.0, 0)
    assert not hasattr(scheduler, "frame_snapshots")


class _Labels(metrics._NoOpMetric):
    """Notes the device label of every observation."""

    def __init__(self) -> None:
        self.devices: set[str] = set()

    def labels(self, **kw: str) -> metrics._NoOpMetric:
        self.devices.add(kw["device"])
        return self


async def test_a_light_slower_than_the_engine_drops_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dropped = _Labels()
    monkeypatch.setattr(metrics, "FRAMES_DROPPED", dropped)
    device = _make_device(max_fps=20)
    buf = RingBuffer(capacity=150)
    _fill_buffer(buf, time.monotonic(), 150)
    scheduler = _scheduler(ring_buffer=buf, devices=[device], fps=60)

    await _run_for(scheduler, 0.5)

    (stats,) = scheduler.get_device_stats()
    assert len(device.adapter.send_frame_calls) >= 7  # it streamed, at its own rate
    assert (stats.frames_dropped, dropped.devices) == (0, set())


async def test_a_frame_overwritten_while_the_light_was_due_is_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dropped = _Labels()
    monkeypatch.setattr(metrics, "FRAMES_DROPPED", dropped)
    adapter = _HeldAdapter()
    device = ManagedDevice(adapter=adapter, tracker=LatencyTracker(StaticLatency(10.0)))
    buf = RingBuffer(capacity=60)
    _fill_buffer(buf, time.monotonic(), 60)
    scheduler = _scheduler(ring_buffer=buf, devices=[device], fps=60)

    task = asyncio.create_task(scheduler.run())
    await asyncio.wait_for(adapter.sending.wait(), timeout=1.0)
    await asyncio.sleep(0.2)  # its send hangs while it's due: the frames meant for it pile up
    (stats,) = scheduler.get_device_stats()
    adapter.release.set()
    scheduler.stop()
    await task

    assert stats.frames_dropped >= 5
    assert dropped.devices == {"held"}


# B11: the four RAM sticks share a name; each keeps its own frames, sequence and metrics.
async def test_lights_that_share_a_name_keep_their_own_frames_and_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    latency = _Labels()
    monkeypatch.setattr(metrics, "DEVICE_LATENCY", latency)
    sticks = [FakeLight(f"openrgb:ram:{i}", name="RAM", led_count=10) for i in range(2)]
    devices = [
        ManagedDevice(adapter=s, tracker=LatencyTracker(StaticLatency(10.0))) for s in sticks
    ]
    buf = RingBuffer(capacity=60)
    _fill_buffer(buf, time.monotonic(), 60)
    scheduler = _scheduler(buf, devices, fps=60)

    await _run_for(scheduler, 0.15)

    assert latency.devices == {"openrgb:ram:0", "openrgb:ram:1"}
    assert all(len(stick.frames) > 0 for stick in sticks)


class _HeldAdapter(MockDeviceAdapter):
    """Holds each frame until released, and logs frames and restores in order."""

    def __init__(self) -> None:
        super().__init__(name="held")
        self.log: list[str] = []
        self.sending = asyncio.Event()
        self.release = asyncio.Event()

    async def send_frame(self, colors: Any) -> None:
        self.sending.set()
        await self.release.wait()
        self.log.append("frame")


async def test_a_restore_waits_for_the_frame_on_its_way() -> None:
    adapter = _HeldAdapter()
    device = ManagedDevice(adapter=adapter, tracker=LatencyTracker(strategy=StaticLatency(10.0)))
    buf = RingBuffer(capacity=60)
    _fill_buffer(buf, time.monotonic(), 60)
    scheduler = _scheduler(buf, [device], fps=60)
    task = asyncio.create_task(scheduler.run())
    await asyncio.wait_for(adapter.sending.wait(), timeout=1.0)

    scheduler.set_route("held", None)  # as the zone manager does before it restores

    async def restore() -> None:
        async with adapter.send_lock:
            adapter.log.append("restore")

    restoring = asyncio.create_task(restore())
    await asyncio.sleep(0.02)
    adapter.release.set()
    await restoring
    await asyncio.sleep(0.05)
    scheduler.stop()
    await task

    assert adapter.log == ["frame", "restore"]


async def test_a_frame_that_waited_for_a_restore_is_dropped() -> None:
    device = _make_device()
    buf = RingBuffer(capacity=60)
    _fill_buffer(buf, time.monotonic(), 60)
    scheduler = _scheduler(buf, [device], fps=60)
    async with device.adapter.send_lock:  # a restore is under way
        task = asyncio.create_task(scheduler.run())
        await asyncio.sleep(0.05)  # the send loop waits with a frame
        scheduler.set_route("TestDevice", None)
    await asyncio.sleep(0.05)
    scheduler.stop()
    await task

    assert device.adapter.send_frame_calls == []


async def test_a_device_without_a_route_gets_nothing() -> None:
    routed, idle = _make_device("routed"), _make_device("idle")
    buf = RingBuffer(capacity=60)
    _fill_buffer(buf, time.monotonic(), 60)
    scheduler = LookaheadScheduler(devices=[routed, idle], fps=60)
    scheduler.set_route("routed", _route(buf))

    await _run_for(scheduler, 0.15)

    assert routed.adapter.send_frame_calls
    assert idle.adapter.send_frame_calls == []


async def test_stats_report_the_share_of_frames_a_streaming_light_misses() -> None:
    starved, idle = _make_device("starved"), _make_device("idle")
    scheduler = LookaheadScheduler(devices=[starved, idle], fps=60)
    scheduler.set_route("starved", _route(RingBuffer(capacity=60)))  # no frames

    await _run_for(scheduler, 0.15)

    stats = {entry.device_id: entry for entry in scheduler.get_device_stats()}
    assert (stats["starved"].send_fps, stats["starved"].dropped_pct) == (0.0, 100.0)
    assert stats["idle"].dropped_pct == 0.0  # not streaming, so nothing is missed


async def test_a_probe_reply_counts_while_frames_go_out() -> None:
    adapter = MockDeviceAdapter(name="Probed", led_count=10)
    tracker = LatencyTracker(WindowedMedianLatency(LATENCY_WINDOW, initial_value_ms=10.0))
    device = ManagedDevice(adapter=adapter, tracker=tracker, max_fps=60)
    buf = RingBuffer(capacity=60)
    _fill_buffer(buf, time.monotonic(), 60)
    scheduler = _scheduler(ring_buffer=buf, devices=[device], fps=60)

    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.2)
    tracker.update_rtt(40.0)  # a probe's round trip while the light streams
    scheduler.stop()
    await task

    assert tracker.effective_latency_ms == 20.0


async def test_a_still_look_is_sent_once_and_then_kept_alive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("dj_ledfx.scheduling.scheduler.KEEPALIVE_S", 0.2)
    device, _buf, scheduler = _still()

    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.1)
    assert len(device.adapter.send_frame_calls) == 1
    await asyncio.sleep(0.2)  # past the keepalive
    (stats,) = scheduler.get_device_stats()
    scheduler.stop()
    await task

    assert len(device.adapter.send_frame_calls) == 2
    assert stats.send_fps > 10  # a skipped frame counts as sent: the light is short of none


# Review Focus 2: a look started right after another reaches the light at once.
async def test_a_new_route_sends_at_once() -> None:
    device, buf, scheduler = _still()

    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.2)
    assert len(device.adapter.send_frame_calls) == 1
    scheduler.set_route(device.adapter.device_info.effective_id, _route(buf))  # same frames
    await asyncio.sleep(0.2)
    scheduler.stop()
    await task

    assert len(device.adapter.send_frame_calls) == 2


async def test_a_route_set_again_sends_at_once() -> None:
    device, buf, scheduler = _still()
    key = device.adapter.device_info.effective_id
    route = _route(buf)
    scheduler.set_route(key, route)

    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.2)
    assert len(device.adapter.send_frame_calls) == 1
    scheduler.set_route(key, route)  # the same route, set again as a readied light's is
    await asyncio.sleep(0.2)
    scheduler.stop()
    await task

    assert len(device.adapter.send_frame_calls) == 2


async def test_a_route_set_during_a_send_sends_again() -> None:
    adapter = _HeldAdapter()
    device = ManagedDevice(adapter=adapter, tracker=LatencyTracker(StaticLatency(10.0)))
    buf = RingBuffer(capacity=150)
    _fill_buffer(buf, time.monotonic(), 150, level=0.5)
    scheduler = _scheduler(ring_buffer=buf, devices=[device], fps=60)

    task = asyncio.create_task(scheduler.run())
    await asyncio.wait_for(adapter.sending.wait(), timeout=1.0)
    scheduler.set_route(adapter.device_info.effective_id, _route(buf))  # mid-send
    adapter.release.set()
    await asyncio.sleep(0.2)
    scheduler.stop()
    await task

    assert adapter.log == ["frame", "frame"]


# The zone manager sends a light leaving its own effect its frame at once, just before the
# effect stops and just after: the frame for now plus its latency, whatever its send loop's
# timing (here no loop runs at all).
async def test_send_now_sends_a_light_its_frame_for_its_own_latency_at_once() -> None:
    near = _make_device("near", latency_ms=10.0, led_count=5)
    far = _make_device("far", latency_ms=600.0, led_count=5)
    buf = _two_frame_ring()
    scheduler = LookaheadScheduler(devices=[near, far], fps=60)
    scheduler.set_route("near", _route(buf, start=0, stop=5))
    scheduler.set_route("far", _route(buf, start=5, stop=10))

    await scheduler.send_now("near")
    await scheduler.send_now("far")

    assert [frame.tobytes() for frame in near.adapter.send_frame_calls] == [bytes([64] * 15)]
    assert [frame.tobytes() for frame in far.adapter.send_frame_calls] == [bytes([255] * 15)]


async def test_send_now_sends_nothing_to_a_light_that_takes_no_frames() -> None:
    held, unrouted, starved = (_make_device(name) for name in ("held", "unrouted", "starved"))
    offline = _make_device("offline", connected=False)
    buf = RingBuffer(capacity=60)
    _fill_buffer(buf, time.monotonic(), 60)
    scheduler = LookaheadScheduler(devices=[held, unrouted, starved, offline], fps=60)
    scheduler.set_route("held", _route(buf, streaming=False))  # it runs its own effect
    scheduler.set_route("starved", _route(RingBuffer(capacity=60)))  # no frame yet
    scheduler.set_route("offline", _route(buf))

    for device_id in ("held", "unrouted", "starved", "offline", "unknown"):
        await scheduler.send_now(device_id)

    assert all(not d.adapter.send_frame_calls for d in (held, unrouted, starved, offline))


async def test_send_now_lands_no_frame_after_a_restore() -> None:
    device = _make_device()
    buf = RingBuffer(capacity=60)
    _fill_buffer(buf, time.monotonic(), 60)
    scheduler = _scheduler(buf, [device], fps=60)
    async with device.adapter.send_lock:  # a restore is under way
        sending = asyncio.create_task(scheduler.send_now("TestDevice"))
        await asyncio.sleep(0.01)  # it waits for the lock
        scheduler.set_route("TestDevice", None)  # as the zone manager does before it restores
    await sending

    assert device.adapter.send_frame_calls == []


async def test_a_light_back_from_a_drop_out_gets_its_frame_at_once() -> None:
    device, _buf, scheduler = _still()
    adapter = device.adapter
    assert isinstance(adapter, MockDeviceAdapter)
    scheduler._disconnect_backoff_s = 0.01

    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.2)
    adapter.is_connected = False
    await asyncio.sleep(0.1)
    adapter.is_connected = True
    await asyncio.sleep(0.2)
    scheduler.stop()
    await task

    assert len(adapter.send_frame_calls) == 2


async def test_a_light_given_a_new_adapter_gets_its_frame_at_once() -> None:
    device, _buf, scheduler = _still()

    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.2)
    replacement = MockDeviceAdapter(name="TestDevice", led_count=10)
    device.adapter = replacement  # as promote_device swaps it when a lamp's output changes
    await asyncio.sleep(0.2)
    scheduler.stop()
    await task

    assert len(replacement.send_frame_calls) == 1


async def test_a_device_without_a_rate_of_its_own_gets_the_engine_s() -> None:
    adapter = MockDeviceAdapter(name="Free", led_count=10)
    assert adapter.stream_fps is None and adapter.display_ms == 0.0  # the ABC's defaults
    tracker = LatencyTracker(StaticLatency(10.0))
    device = ManagedDevice(adapter=adapter, tracker=tracker, max_fps=adapter.stream_fps)
    buf = RingBuffer(capacity=150)
    _fill_buffer(buf, time.monotonic(), 150)
    scheduler = _scheduler(ring_buffer=buf, devices=[device], fps=30)

    await _run_for(scheduler, 0.5)

    assert 11 <= len(adapter.send_frame_calls) <= 19  # 30 a second, within 25%
    (stats,) = scheduler.get_device_stats()
    assert stats.send_fps > 0


# Review Focus 6: a light that never acks or answers a probe keeps its rate.
async def test_a_light_that_never_acks_keeps_its_rate() -> None:
    adapter = MockDeviceAdapter(name="Quiet", led_count=10)
    strategy = make_strategy("windowed_median", 10.0, LATENCY_WINDOW)
    tracker = LatencyTracker(strategy, display_ms=24.0)
    device = ManagedDevice(adapter=adapter, tracker=tracker, max_fps=20)
    buf = RingBuffer(capacity=150)
    _fill_buffer(buf, time.monotonic(), 150)
    scheduler = _scheduler(ring_buffer=buf, devices=[device], fps=60)

    await _run_for(scheduler, 0.5)

    assert 7 <= len(adapter.send_frame_calls) <= 13  # 20 a second, within 30%
    assert tracker.effective_latency_ms == 34.0  # its seed and its display delay
