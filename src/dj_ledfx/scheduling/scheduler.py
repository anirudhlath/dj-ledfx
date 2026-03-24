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
from dj_ledfx.events import DeviceOfflineEvent, EventBus, TransportStateChangedEvent
from dj_ledfx.spatial.compositor import SpatialCompositor
from dj_ledfx.transport import TransportState
from dj_ledfx.types import DeviceStats

if TYPE_CHECKING:
    from dj_ledfx.devices.adapter import DeviceAdapter
    from dj_ledfx.persistence.state_db import StateDB
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
        event_bus: EventBus | None = None,
        state_db: StateDB | None = None,
    ) -> None:
        self._ring_buffer = ring_buffer
        self._frame_period = 1.0 / fps
        self._disconnect_backoff_s = disconnect_backoff_s
        self._running = False
        self._start_time: float = 0.0
        self._compositor = compositor
        self._event_bus = event_bus
        self._state_db = state_db
        self._frame_snapshots: dict[str, tuple[NDArray[np.uint8], int]] = {}
        self._frame_seq: dict[str, int] = {}
        self._transport_state = TransportState.STOPPED
        self._resume_event = asyncio.Event()
        self._restore_task: asyncio.Task[None] | None = None
        if event_bus is not None:
            event_bus.subscribe(TransportStateChangedEvent, self._on_transport_changed)

        # Dict-based device state, keyed by stable_id (or name as fallback)
        self._device_state: dict[str, DeviceSendState] = {}
        for device in devices:
            key = device.adapter.device_info.effective_id
            self._device_state[key] = DeviceSendState(managed=device, slot=FrameSlot())

    @staticmethod
    def _device_key(managed: ManagedDevice) -> str:
        return managed.adapter.device_info.effective_id

    @property
    def frame_snapshots(self) -> dict[str, tuple[NDArray[np.uint8], int]]:
        return self._frame_snapshots

    @property
    def compositor(self) -> SpatialCompositor | None:
        return self._compositor

    @compositor.setter
    def compositor(self, value: SpatialCompositor | None) -> None:
        self._compositor = value

    @property
    def transport_state(self) -> TransportState:
        return self._transport_state

    def _on_transport_changed(self, event: TransportStateChangedEvent) -> None:
        self._transport_state = event.new_state
        if event.new_state.is_active:
            self._resume_event.set()
        else:
            self._resume_event.clear()
            # Restore saved device states when transitioning from active -> STOPPED
            if event.old_state.is_active and self._state_db is not None:
                if self._restore_task is not None and not self._restore_task.done():
                    self._restore_task.cancel()
                self._restore_task = asyncio.create_task(self._restore_device_states())

    async def _restore_device_states(self) -> None:
        """Restore all connected devices to their saved pre-effect states."""
        assert self._state_db is not None
        saved_states = await self._state_db.load_all_device_states()
        if not saved_states:
            return

        async def _restore_one(adapter: DeviceAdapter, state_bytes: bytes) -> None:
            try:
                await adapter.restore_state(state_bytes)
                logger.debug(
                    "Restored state for device '{}' (stable_id={})",
                    adapter.device_info.name,
                    adapter.device_info.effective_id,
                )
            except Exception:
                logger.warning(
                    "Failed to restore state for device '{}'",
                    adapter.device_info.name,
                )

        tasks = []
        for state in self._device_state.values():
            adapter = state.managed.adapter
            if not adapter.is_connected:
                continue
            state_bytes = saved_states.get(adapter.device_info.effective_id)
            if state_bytes is not None:
                tasks.append(_restore_one(adapter, state_bytes))
        if tasks:
            await asyncio.gather(*tasks)

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

    def set_device_pipeline(self, stable_id: str, pipeline: ScenePipeline | None) -> None:
        """Assign (or clear) a per-device ScenePipeline by stable_id."""
        state = self._device_state.get(stable_id)
        if state is None:
            logger.warning("Scheduler: set_device_pipeline called for unknown key '{}'", stable_id)
            return
        state.pipeline = pipeline

    def has_device(self, stable_id: str) -> bool:
        """Check if a device is registered in the scheduler."""
        return stable_id in self._device_state

    def remove_pipeline_refs(self, scene_id: str) -> None:
        """Null out pipeline for all devices referencing the given scene."""
        for state in self._device_state.values():
            if state.pipeline is not None and state.pipeline.scene_id == scene_id:
                state.pipeline = None

    def stop(self) -> None:
        self._running = False
        self._resume_event.set()

    async def run(self) -> None:
        self._running = True
        self._start_time = time.monotonic()
        logger.info(
            "LookaheadScheduler started with {} devices",
            len(self._device_state),
        )

        # Spawn per-device send loops (snapshot to avoid mutation during iteration)
        for key, state in list(self._device_state.items()):
            state.send_task = asyncio.create_task(self._send_loop(state, key))

        try:
            # Run distributor loop — gated by transport state
            while self._running:
                await self._resume_event.wait()
                last_tick = time.monotonic()
                while self._running and self._resume_event.is_set():
                    now = time.monotonic()
                    for state in self._device_state.values():
                        slot = state.slot
                        device = state.managed
                        if slot.has_pending:
                            logger.trace(
                                "Frame overwritten for '{}' — device draining slower than engine",
                                device.adapter.device_info.name,
                            )
                            metrics.FRAMES_DROPPED.labels(
                                device=device.adapter.device_info.name
                            ).inc()
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
            # Snapshot to guard against concurrent add_device/remove_device calls
            all_states = list(self._device_state.values())
            all_tasks = [s.send_task for s in all_states if s.send_task is not None]
            for task in all_tasks:
                task.cancel()
            await asyncio.gather(*all_tasks, return_exceptions=True)
            # Clear task refs
            for state in all_states:
                state.send_task = None

        logger.info("LookaheadScheduler stopped")

    async def _send_loop(self, state: DeviceSendState, key: str) -> None:
        device = state.managed
        slot = state.slot
        was_connected = device.adapter.is_connected
        last_send_time = time.monotonic()

        while self._running and key in self._device_state:
            if not self._resume_event.is_set():
                await self._resume_event.wait()
                if not self._running:
                    break
            if not device.adapter.is_connected:
                if was_connected:
                    logger.warning(
                        "Device '{}' disconnected",
                        device.adapter.device_info.name,
                    )
                    if self._event_bus is not None:
                        self._event_bus.emit(
                            DeviceOfflineEvent(
                                stable_id=device.adapter.device_info.stable_id or key,
                                name=device.adapter.device_info.name,
                            )
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

            try:
                target_time = await slot.take(timeout=1.0)
            except TimeoutError:
                continue

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

            colors = frame.colors
            compositor = (
                state.pipeline.compositor if state.pipeline is not None else self._compositor
            )
            if compositor is not None:
                mapped = compositor.composite(frame.colors, device.adapter.device_info.name)
                if mapped is not None:
                    colors = mapped

            device_name = device.adapter.device_info.name

            # Gate actual device send on transport state
            if self._transport_state == TransportState.PLAYING:
                send_start = time.monotonic()
                try:
                    await device.adapter.send_frame(colors)
                except Exception:
                    logger.warning("Send failed for '{}'", device_name)
                    continue

                send_elapsed = time.monotonic() - send_start
                metrics.DEVICE_SEND_DURATION.labels(device=device_name).observe(send_elapsed)

                if device.adapter.supports_latency_probing:
                    rtt_ms = send_elapsed * 1000.0
                    device.tracker.update(rtt_ms)

                state.send_count += 1
                metrics.DEVICE_LATENCY.labels(device=device_name).set(
                    device.tracker.effective_latency_s
                )
                metrics.DEVICE_FPS.labels(device=device_name).set(device.max_fps)

            # Always update frame snapshots (needed for WS preview in SIMULATING mode)
            seq = self._frame_seq.get(device_name, 0) + 1
            self._frame_seq[device_name] = seq
            self._frame_snapshots[device_name] = (colors, seq)

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
