from __future__ import annotations

import asyncio
import time

from loguru import logger

from dj_ledfx import metrics
from dj_ledfx.devices.manager import ManagedDevice
from dj_ledfx.effects.engine import RingBuffer
from dj_ledfx.types import DeviceStats


class FrameSlot:
    """Depth-1 slot for passing target_time from distributor to per-device send loop.

    Stores a target_time (float), not a frame. The send loop resolves it to
    a frame via ring_buffer.find_nearest() only when ready to send.
    """

    def __init__(self) -> None:
        self._event = asyncio.Event()
        self._target_time: float = 0.0
        self._put_count: int = 0

    def put(self, target_time: float) -> None:
        """Write target_time and signal. Must not await — single synchronous step."""
        self._target_time = target_time
        self._put_count += 1
        self._event.set()

    async def take(self, timeout: float = 1.0) -> float:
        """Wait for a target_time. Raises asyncio.TimeoutError on timeout."""
        await asyncio.wait_for(self._event.wait(), timeout=timeout)
        self._event.clear()
        return self._target_time

    @property
    def has_pending(self) -> bool:
        return self._event.is_set()

    @property
    def put_count(self) -> int:
        return self._put_count


class LookaheadScheduler:
    def __init__(
        self,
        ring_buffer: RingBuffer,
        devices: list[ManagedDevice],
        fps: int = 60,
        disconnect_backoff_s: float = 1.0,
    ) -> None:
        self._ring_buffer = ring_buffer
        self._devices = devices
        self._frame_period = 1.0 / fps
        self._disconnect_backoff_s = disconnect_backoff_s
        self._running = False
        self._slots = [FrameSlot() for _ in devices]
        self._send_tasks: list[asyncio.Task[None]] = []
        self._send_counts: list[int] = [0] * len(devices)
        self._start_time: float = 0.0

    def stop(self) -> None:
        self._running = False

    async def run(self) -> None:
        self._running = True
        self._start_time = time.monotonic()
        logger.info(
            "LookaheadScheduler started with {} devices",
            len(self._devices),
        )

        # Spawn per-device send loops
        for i, (device, slot) in enumerate(zip(self._devices, self._slots, strict=True)):
            task = asyncio.create_task(self._send_loop(device, slot, i))
            self._send_tasks.append(task)

        try:
            # Run distributor loop
            last_tick = time.monotonic()
            while self._running:
                now = time.monotonic()
                for device, slot in zip(self._devices, self._slots, strict=True):
                    if slot.has_pending:
                        logger.trace(
                            "Frame overwritten for '{}' — device draining slower than engine",
                            device.adapter.device_info.name,
                        )
                        metrics.FRAMES_DROPPED.labels(device=device.adapter.device_info.name).inc()
                    target_time = now + device.tracker.effective_latency_s
                    slot.put(target_time)

                last_tick += self._frame_period
                sleep_time = last_tick - time.monotonic()
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    last_tick = time.monotonic()
                    await asyncio.sleep(0)
        finally:
            # Clean up child tasks — runs on both normal exit and CancelledError
            for task in self._send_tasks:
                task.cancel()
            await asyncio.gather(*self._send_tasks, return_exceptions=True)
            self._send_tasks.clear()

        logger.info("LookaheadScheduler stopped")

    async def _send_loop(self, device: ManagedDevice, slot: FrameSlot, index: int) -> None:
        was_connected = device.adapter.is_connected
        last_send_time = time.monotonic()
        device_name = device.adapter.device_info.name

        while self._running:
            # Step 1: Check connection
            if not device.adapter.is_connected:
                if was_connected:
                    logger.warning(
                        "Device '{}' disconnected",
                        device.adapter.device_info.name,
                    )
                was_connected = False
                await asyncio.sleep(self._disconnect_backoff_s)
                continue

            # Reconnection detection
            if not was_connected:
                logger.info(
                    "Device '{}' reconnected",
                    device.adapter.device_info.name,
                )
                device.tracker.reset()
                was_connected = True

            # Step 2: Wait for target_time
            try:
                target_time = await slot.take(timeout=1.0)
            except TimeoutError:
                continue

            # Step 3: Find nearest frame (numpy copy happens here)
            frame = self._ring_buffer.find_nearest(target_time)
            if frame is None:
                logger.warning(
                    "No frame in ring buffer for '{}' (target_time={:.3f})",
                    device.adapter.device_info.name,
                    target_time,
                )
                continue

            # Steps 4-5: Send frame
            send_start = time.monotonic()
            try:
                await device.adapter.send_frame(frame.colors)
            except Exception:
                logger.warning(
                    "Send failed for '{}'",
                    device.adapter.device_info.name,
                )
                continue

            send_elapsed = time.monotonic() - send_start
            metrics.DEVICE_SEND_DURATION.labels(device=device_name).observe(send_elapsed)

            # Step 6: Increment send count
            self._send_counts[index] += 1
            metrics.DEVICE_LATENCY.labels(device=device_name).set(
                device.tracker.effective_latency_s
            )
            metrics.DEVICE_FPS.labels(device=device_name).set(device.max_fps)

            # Step 7: RTT update (only if adapter supports probing)
            if device.adapter.supports_latency_probing:
                rtt_ms = (time.monotonic() - send_start) * 1000.0
                device.tracker.update(rtt_ms)

            # Step 8: FPS cap — advance by fixed interval to absorb sleep overshoot
            min_frame_interval = 1.0 / device.max_fps
            last_send_time += min_frame_interval
            remaining = last_send_time - time.monotonic()
            if remaining > 0:
                await asyncio.sleep(remaining)
            else:
                # Fell behind — snap to now to avoid burst catch-up
                last_send_time = time.monotonic()

    def get_device_stats(self) -> list[DeviceStats]:
        """Snapshot of per-device send statistics."""
        now = time.monotonic()
        elapsed = now - self._start_time if self._start_time > 0 else 1.0
        stats: list[DeviceStats] = []
        for i, (device, slot) in enumerate(zip(self._devices, self._slots, strict=True)):
            send_fps = self._send_counts[i] / elapsed if elapsed > 0 else 0.0
            frames_dropped = slot.put_count - self._send_counts[i]
            stats.append(
                DeviceStats(
                    device_name=device.adapter.device_info.name,
                    effective_latency_ms=device.tracker.effective_latency_ms,
                    send_fps=send_fps,
                    frames_dropped=max(0, frames_dropped),
                )
            )
        return stats
