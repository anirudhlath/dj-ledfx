from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from loguru import logger
from numpy.typing import NDArray

from dj_ledfx import metrics
from dj_ledfx.devices.manager import ManagedDevice
from dj_ledfx.effects.engine import RingBuffer
from dj_ledfx.spatial.compositor import SpatialCompositor
from dj_ledfx.types import DeviceStats

if TYPE_CHECKING:
    from dj_ledfx.spatial.pipeline import ScenePipeline


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


@dataclass
class DeviceSendState:
    """Per-device send state, keyed by stable_id."""

    managed: ManagedDevice
    slot: FrameSlot
    send_count: int = 0
    send_task: asyncio.Task[None] | None = None
    pipeline: ScenePipeline | None = None


class LookaheadScheduler:
    def __init__(
        self,
        ring_buffer: RingBuffer,
        devices: list[ManagedDevice],
        fps: int = 60,
        disconnect_backoff_s: float = 1.0,
        compositor: SpatialCompositor | None = None,
    ) -> None:
        self._ring_buffer = ring_buffer
        self._frame_period = 1.0 / fps
        self._disconnect_backoff_s = disconnect_backoff_s
        self._running = False
        self._start_time: float = 0.0
        self._compositor = compositor
        self._frame_snapshots: dict[str, tuple[NDArray[np.uint8], int]] = {}
        self._frame_seq: dict[str, int] = {}

        # Dict-based device state, keyed by stable_id (or name as fallback)
        self._device_state: dict[str, DeviceSendState] = {}
        for device in devices:
            key = device.adapter.device_info.stable_id or device.adapter.device_info.name
            self._device_state[key] = DeviceSendState(managed=device, slot=FrameSlot())

    @staticmethod
    def _device_key(managed: ManagedDevice) -> str:
        return managed.adapter.device_info.stable_id or managed.adapter.device_info.name

    @property
    def frame_snapshots(self) -> dict[str, tuple[NDArray[np.uint8], int]]:
        return self._frame_snapshots

    @property
    def compositor(self) -> SpatialCompositor | None:
        return self._compositor

    @compositor.setter
    def compositor(self, value: SpatialCompositor | None) -> None:
        self._compositor = value

    def add_device(self, managed: ManagedDevice, pipeline: ScenePipeline | None = None) -> None:
        """Add a device dynamically. Spawns a send task if the scheduler is running."""
        key = self._device_key(managed)
        if key in self._device_state:
            logger.warning("Device '{}' already in scheduler, skipping add", key)
            return
        state = DeviceSendState(managed=managed, slot=FrameSlot(), pipeline=pipeline)
        self._device_state[key] = state
        if self._running:
            state.send_task = asyncio.create_task(self._send_loop(state, key))
        logger.info("Scheduler: added device '{}'", key)

    def remove_device(self, stable_id: str) -> None:
        """Remove a device by stable_id (or name). Cancels its send task."""
        state = self._device_state.pop(stable_id, None)
        if state is None:
            logger.warning("Scheduler: remove_device called for unknown key '{}'", stable_id)
            return
        if state.send_task is not None and not state.send_task.done():
            state.send_task.cancel()
        logger.info("Scheduler: removed device '{}'", stable_id)

    def stop(self) -> None:
        self._running = False

    async def run(self) -> None:
        self._running = True
        self._start_time = time.monotonic()
        logger.info(
            "LookaheadScheduler started with {} devices",
            len(self._device_state),
        )

        # Spawn per-device send loops
        for key, state in self._device_state.items():
            state.send_task = asyncio.create_task(self._send_loop(state, key))

        try:
            # Run distributor loop
            last_tick = time.monotonic()
            while self._running:
                now = time.monotonic()
                for state in list(self._device_state.values()):
                    slot = state.slot
                    device = state.managed
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
            all_tasks = [
                state.send_task
                for state in self._device_state.values()
                if state.send_task is not None
            ]
            for task in all_tasks:
                task.cancel()
            await asyncio.gather(*all_tasks, return_exceptions=True)
            # Clear task refs
            for state in self._device_state.values():
                state.send_task = None

        logger.info("LookaheadScheduler stopped")

    async def _send_loop(self, state: DeviceSendState, key: str) -> None:
        device = state.managed
        slot = state.slot
        was_connected = device.adapter.is_connected
        last_send_time = time.monotonic()
        device_name = device.adapter.device_info.name

        while self._running and key in self._device_state:
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
            # Use pipeline's ring buffer if available, else scheduler's
            ring_buf = (
                state.pipeline.ring_buffer if state.pipeline is not None else self._ring_buffer
            )
            frame = ring_buf.find_nearest(target_time)
            if frame is None:
                logger.warning(
                    "No frame in ring buffer for '{}' (target_time={:.3f})",
                    device.adapter.device_info.name,
                    target_time,
                )
                continue

            # Steps 4-5: Send frame (with optional spatial compositing)
            colors = frame.colors
            # Use pipeline's compositor if pipeline set, else scheduler-level compositor
            compositor = (
                state.pipeline.compositor if state.pipeline is not None else self._compositor
            )
            if compositor is not None:
                mapped = compositor.composite(frame.colors, device.adapter.device_info.name)
                if mapped is not None:
                    colors = mapped
            send_start = time.monotonic()
            try:
                await device.adapter.send_frame(colors)
            except Exception:
                logger.warning(
                    "Send failed for '{}'",
                    device.adapter.device_info.name,
                )
                continue

            send_elapsed = time.monotonic() - send_start
            metrics.DEVICE_SEND_DURATION.labels(device=device_name).observe(send_elapsed)

            # Step 6: Increment send count and store snapshot
            state.send_count += 1
            seq = self._frame_seq.get(device_name, 0) + 1
            self._frame_seq[device_name] = seq
            self._frame_snapshots[device_name] = (colors, seq)
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
        for state in self._device_state.values():
            device = state.managed
            send_fps = state.send_count / elapsed if elapsed > 0 else 0.0
            frames_dropped = state.slot.put_count - state.send_count
            stats.append(
                DeviceStats(
                    device_name=device.adapter.device_info.name,
                    effective_latency_ms=device.tracker.effective_latency_ms,
                    send_fps=send_fps,
                    frames_dropped=max(0, frames_dropped),
                    connected=device.adapter.is_connected,
                )
            )
        return stats
