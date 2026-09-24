"""Sends each light its slice of its zone's frames, ahead by the light's latency (spec §4.1)."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
from loguru import logger
from numpy.typing import NDArray

from dj_ledfx import metrics
from dj_ledfx.devices.manager import ManagedDevice
from dj_ledfx.events import DeviceOfflineEvent, EventBus
from dj_ledfx.types import DeviceStats

if TYPE_CHECKING:
    from collections.abc import Sequence

    from dj_ledfx.scheduling.route import DeviceRoute

RATE_WINDOW_S = 1.0  # send_fps and dropped_pct cover the last second


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


def _trim(sent_at: deque[float], now: float) -> None:
    while sent_at and now - sent_at[0] > RATE_WINDOW_S:
        sent_at.popleft()


@dataclass
class DeviceSendState:
    """Per-device send state, keyed by stable_id."""

    managed: ManagedDevice
    slot: FrameSlot
    send_count: int = 0
    send_task: asyncio.Task[None] | None = None
    sent_at: deque[float] = field(default_factory=deque)  # send times in the last second


class LookaheadScheduler:
    """Sends each device the slice its route points at, for now plus the device's latency.

    The zone manager sets the routes: this is its RouteTable. A device with no route gets
    nothing. A route that doesn't stream (the light runs its own effect, isn't ready yet,
    or preview-only is on) sends nothing either, but its slice still reaches the web
    preview.
    """

    def __init__(
        self,
        devices: Sequence[ManagedDevice] = (),
        fps: int = 60,
        disconnect_backoff_s: float = 1.0,
        event_bus: EventBus | None = None,
    ) -> None:
        self._fps = fps
        self._frame_period = 1.0 / fps
        self._disconnect_backoff_s = disconnect_backoff_s
        self._running = False
        self._event_bus = event_bus
        self._routes: dict[str, DeviceRoute] = {}
        self._frame_snapshots: dict[str, tuple[NDArray[np.uint8], int]] = {}
        self._frame_seq: dict[str, int] = {}
        self._device_state: dict[str, DeviceSendState] = {}
        for device in devices:
            key = self._device_key(device)
            self._device_state[key] = DeviceSendState(managed=device, slot=FrameSlot())

    @staticmethod
    def _device_key(managed: ManagedDevice) -> str:
        return managed.adapter.device_info.effective_id

    @property
    def frame_snapshots(self) -> dict[str, tuple[NDArray[np.uint8], int]]:
        return self._frame_snapshots

    def set_route(self, device_id: str, route: DeviceRoute | None) -> None:
        """Where a device's frames come from; None stops them."""
        if route is None:
            self._routes.pop(device_id, None)
        else:
            self._routes[device_id] = route

    def add_device(self, managed: ManagedDevice) -> None:
        """Add a device dynamically. Spawns a send task if the scheduler is running."""
        key = self._device_key(managed)
        if key in self._device_state:
            logger.warning("Device '{}' already in scheduler, skipping add", key)
            return
        state = DeviceSendState(managed=managed, slot=FrameSlot())
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

    def has_device(self, stable_id: str) -> bool:
        return stable_id in self._device_state

    def stop(self) -> None:
        self._running = False

    async def run(self) -> None:
        self._running = True
        logger.info("LookaheadScheduler started with {} devices", len(self._device_state))
        for key, state in list(self._device_state.items()):
            state.send_task = asyncio.create_task(self._send_loop(state, key))
        try:
            last_tick = time.monotonic()
            while self._running:
                self._distribute(time.monotonic())
                last_tick += self._frame_period
                sleep_time = last_tick - time.monotonic()
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    last_tick = time.monotonic()
                    await asyncio.sleep(0)
        finally:
            # Runs on normal exit and on cancellation. Snapshot: devices may come and go.
            all_states = list(self._device_state.values())
            all_tasks = [s.send_task for s in all_states if s.send_task is not None]
            for task in all_tasks:
                task.cancel()
            await asyncio.gather(*all_tasks, return_exceptions=True)
            for state in all_states:
                state.send_task = None
        logger.info("LookaheadScheduler stopped")

    def _distribute(self, now: float) -> None:
        """Tell each routed device which moment its next frame is for: now + its latency."""
        for key, state in self._device_state.items():
            if key not in self._routes:
                continue
            if state.slot.has_pending:
                logger.trace("Frame overwritten for '{}': it drains slower than the engine", key)
                metrics.FRAMES_DROPPED.labels(device=key).inc()
            state.slot.put(now + state.managed.tracker.effective_latency_s)

    async def _send_loop(self, state: DeviceSendState, key: str) -> None:
        device = state.managed
        slot = state.slot
        was_connected = device.adapter.is_connected
        last_send_time = time.monotonic()

        while self._running and key in self._device_state:
            if not device.adapter.is_connected:
                if was_connected:
                    logger.warning("Device '{}' disconnected", device.adapter.device_info.name)
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

            if not was_connected:
                logger.info("Device '{}' reconnected", device.adapter.device_info.name)
                device.tracker.reset()
                was_connected = True

            try:
                target_time = await slot.take(timeout=1.0)
            except TimeoutError:
                continue

            route = self._routes.get(key)
            if route is None:
                continue
            colors = route.colors_at(target_time, device.adapter.led_count)
            device_name = device.adapter.device_info.name
            if colors is None:
                logger.trace("No frame yet for '{}' (target {:.3f})", device_name, target_time)
                continue

            if route.streaming:
                async with device.adapter.send_lock:
                    current = self._routes.get(key)  # a restore may have run meanwhile
                    if current is None or not current.streaming:
                        continue
                    send_start = time.monotonic()
                    try:
                        await device.adapter.send_frame(colors)
                    except Exception:
                        logger.warning("Send failed for '{}'", device_name)
                        continue
                sent = time.monotonic()
                metrics.DEVICE_SEND_DURATION.labels(device=key).observe(sent - send_start)
                if device.adapter.supports_latency_probing:
                    device.tracker.update((sent - send_start) * 1000.0)
                state.send_count += 1
                state.sent_at.append(sent)
                _trim(state.sent_at, sent)
                metrics.DEVICE_LATENCY.labels(device=key).set(device.tracker.effective_latency_s)
                metrics.DEVICE_FPS.labels(device=key).set(device.max_fps)

            # The web preview shows every routed device's slice, sent or not, by stable id:
            # lights may share a name (the four RAM sticks).
            seq = self._frame_seq.get(key, 0) + 1
            self._frame_seq[key] = seq
            self._frame_snapshots[key] = (colors, seq)

            last_send_time += 1.0 / device.max_fps
            remaining = last_send_time - time.monotonic()
            if remaining > 0:
                await asyncio.sleep(remaining)
            else:  # fell behind: snap to now rather than burst to catch up
                last_send_time = time.monotonic()

    def get_device_stats(self) -> list[DeviceStats]:
        """Per-device send statistics; rates cover the last second."""
        now = time.monotonic()
        stats: list[DeviceStats] = []
        for key, state in self._device_state.items():
            device = state.managed
            _trim(state.sent_at, now)
            send_fps = float(len(state.sent_at))
            stats.append(
                DeviceStats(
                    device_name=device.adapter.device_info.name,
                    effective_latency_ms=device.tracker.effective_latency_ms,
                    send_fps=send_fps,
                    frames_dropped=max(0, state.slot.put_count - state.send_count),
                    connected=device.adapter.is_connected,
                    device_id=key,
                    dropped_pct=self._dropped_pct(key, state, send_fps),
                )
            )
        return stats

    def _dropped_pct(self, key: str, state: DeviceSendState, send_fps: float) -> float:
        """How far a streaming light falls short of the frames it should get, in percent."""
        route = self._routes.get(key)
        if route is None or not route.streaming or not state.managed.adapter.is_connected:
            return 0.0
        expected = min(self._fps, state.managed.max_fps)
        return max(0.0, 1.0 - send_fps / expected) * 100.0
