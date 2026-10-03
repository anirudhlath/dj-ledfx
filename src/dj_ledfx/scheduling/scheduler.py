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
from dj_ledfx.timing import paced, trim_window
from dj_ledfx.types import DeviceStats

# A frame equal to the last one sent goes out again only this often: the light already shows
# it, and a lamp that drops a packet gets it back within a second. A route set again, a new
# adapter or a drop-out sends it at once.
KEEPALIVE_S = 1.0

if TYPE_CHECKING:
    from collections.abc import Sequence

    from dj_ledfx.devices.adapter import DeviceAdapter
    from dj_ledfx.scheduling.route import DeviceRoute


class FrameSlot:
    """Depth-1 slot for passing target_time from distributor to per-device send loop.

    Stores a target_time (float), not a frame. The send loop resolves it to
    a frame via ring_buffer.find_nearest() only when ready to send.
    """

    def __init__(self) -> None:
        self._event = asyncio.Event()
        self._target_time: float = 0.0

    def put(self, target_time: float) -> None:
        """Write target_time and signal. Must not await — single synchronous step."""
        self._target_time = target_time
        self._event.set()

    async def take(self, timeout: float = 1.0) -> float:
        """Wait for a target_time. Raises asyncio.TimeoutError on timeout."""
        await asyncio.wait_for(self._event.wait(), timeout=timeout)
        self._event.clear()
        return self._target_time

    def discard(self) -> None:
        """Forget a pending target_time: one written before a drop-out is stale."""
        self._event.clear()

    @property
    def has_pending(self) -> bool:
        return self._event.is_set()


@dataclass(frozen=True, slots=True)
class LastSend:
    """The last frame a device was sent: through which adapter, its bytes, and when."""

    adapter: DeviceAdapter
    data: bytes
    at: float


@dataclass
class DeviceSendState:
    """Per-device send state, keyed by stable_id."""

    managed: ManagedDevice
    slot: FrameSlot
    send_count: int = 0
    send_task: asyncio.Task[None] | None = None
    sent_at: deque[float] = field(default_factory=deque)  # send times in the last second
    last: LastSend | None = None  # None: the next frame goes out, whatever it is
    due_at: float = 0.0  # when the send loop next wakes for a frame (monotonic)
    dropped: int = 0  # frames overwritten untaken a period after it was due


class LookaheadScheduler:
    """Sends each device the slice its route points at, for now plus the device's latency.

    The zone manager sets the routes: this is its RouteTable. A device with no route, or a
    route that doesn't stream (the light runs its own effect, isn't ready yet, or
    preview-only is on), gets nothing, and nothing is read for it. The web app's frames
    come from the rings (zones/frames.py), not from here.
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
        self._device_state: dict[str, DeviceSendState] = {}
        for device in devices:
            key = self._device_key(device)
            self._device_state[key] = DeviceSendState(managed=device, slot=FrameSlot())

    @staticmethod
    def _device_key(managed: ManagedDevice) -> str:
        return managed.adapter.device_info.effective_id

    def set_route(self, device_id: str, route: DeviceRoute | None) -> None:
        """Where a device's frames come from; None stops them. A route set (the light may
        have been readied again) sends its next frame, even one the light showed before."""
        if route is None:
            self._routes.pop(device_id, None)
        else:
            self._routes[device_id] = route
        state = self._device_state.get(device_id)
        if state is not None:
            state.last = None

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
            await paced(self._frame_period, self._distribute, lambda: self._running)
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
        """Tell each streaming device which moment its next frame is for: now plus its
        latency. A device is written from the tick before its send loop wakes, so a light
        slower than the engine is written about as often as it sends; a frame still untaken a
        whole period after the light was due is overwritten, and that's a frame dropped."""
        period = self._frame_period
        for key, state in self._device_state.items():
            route = self._routes.get(key)
            if route is None or not route.streaming or not state.managed.adapter.is_connected:
                continue
            if now < state.due_at - period:
                continue  # it isn't due yet: this frame would only be overwritten
            if state.slot.has_pending and now >= state.due_at + period:
                logger.trace("Frame dropped for '{}': it was due and didn't take it", key)
                state.dropped += 1
                metrics.FRAMES_DROPPED.labels(device=key).inc()
            state.slot.put(now + state.managed.tracker.effective_latency_s)

    async def _send_loop(self, state: DeviceSendState, key: str) -> None:
        device = state.managed
        slot = state.slot
        was_connected = device.adapter.is_connected
        last_send_time = time.monotonic()

        while self._running and key in self._device_state:
            if not device.adapter.is_connected:
                state.last = None  # a light back from a drop-out gets its frame at once
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
                state.due_at = time.monotonic() + self._disconnect_backoff_s  # none till then
                await asyncio.sleep(self._disconnect_backoff_s)
                continue

            if not was_connected:
                logger.info("Device '{}' reconnected", device.adapter.device_info.name)
                device.tracker.reset()
                slot.discard()  # its frame comes from the next tick
                was_connected = True

            try:
                target_time = await slot.take(timeout=1.0)
            except TimeoutError:
                continue

            route = self._routes.get(key)
            if route is None or not route.streaming:
                continue  # it stopped streaming after the slot was filled
            colors = route.colors_at(target_time, device.adapter.led_count)
            if colors is None:
                logger.trace(
                    "No frame yet for '{}' (target {:.3f})",
                    device.adapter.device_info.name,
                    target_time,
                )
                continue

            data = colors.tobytes()
            now = time.monotonic()
            last = state.last
            shown = (  # the light shows this already: it counts as sent, and nothing goes out
                last is not None
                and now - last.at < KEEPALIVE_S
                and device.adapter is last.adapter
                and data == last.data
            )
            if not shown:
                sent = await self._send(state, key, colors, data)
                if sent is None:
                    continue
                now = sent
            state.send_count += 1
            state.sent_at.append(now)
            trim_window(state.sent_at, now)

            # The next frame is due a period on; a loop that fell behind starts again from now
            # rather than bursting to catch up.
            now = time.monotonic()
            last_send_time = max(last_send_time + 1.0 / device.max_fps, now)
            state.due_at = last_send_time
            if last_send_time > now:
                await asyncio.sleep(last_send_time - now)

    async def _send(
        self, state: DeviceSendState, key: str, colors: NDArray[np.uint8], data: bytes
    ) -> float | None:
        """Send a device its frame under its adapter's send lock. When it went out, or None:
        the route stopped streaming meanwhile (a restore may have run), or the send failed."""
        device = state.managed
        adapter = device.adapter
        async with adapter.send_lock:
            route = self._routes.get(key)
            if route is None or not route.streaming:
                return None
            send_start = time.monotonic()
            try:
                await adapter.send_frame(colors)
            except Exception:
                logger.warning("Send failed for '{}'", adapter.device_info.name)
                return None
        sent = time.monotonic()
        device.tracker.note_send()  # its probes' round trips count from now
        # A route set while the frame went out may have readied the light again: the next
        # frame goes out whatever it is, as it would had the route been set before.
        rerouted = self._routes.get(key) is not route
        state.last = None if rerouted else LastSend(adapter, data, sent)
        metrics.DEVICE_SEND_DURATION.labels(device=key).observe(sent - send_start)
        metrics.DEVICE_LATENCY.labels(device=key).set(device.tracker.effective_latency_s)
        metrics.DEVICE_FPS.labels(device=key).set(device.max_fps)
        return sent

    def get_device_stats(self) -> list[DeviceStats]:
        """Per-device send statistics; rates cover the last second."""
        now = time.monotonic()
        stats: list[DeviceStats] = []
        for key, state in self._device_state.items():
            device = state.managed
            trim_window(state.sent_at, now)
            send_fps = float(len(state.sent_at))
            stats.append(
                DeviceStats(
                    device_name=device.adapter.device_info.name,
                    effective_latency_ms=device.tracker.effective_latency_ms,
                    send_fps=send_fps,
                    frames_dropped=state.dropped,
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
