from __future__ import annotations

import asyncio
import time

from loguru import logger

from dj_ledfx.devices.manager import ManagedDevice
from dj_ledfx.effects.engine import RingBuffer


class LookaheadScheduler:
    def __init__(
        self,
        ring_buffer: RingBuffer,
        devices: list[ManagedDevice],
        fps: int = 60,
    ) -> None:
        self._ring_buffer = ring_buffer
        self._devices = devices
        self._frame_period = 1.0 / fps
        self._running = False

    def stop(self) -> None:
        self._running = False

    async def run(self) -> None:
        self._running = True
        logger.info(
            "LookaheadScheduler started with {} devices",
            len(self._devices),
        )

        while self._running:
            tick_start = time.monotonic()
            await self._dispatch_all()
            elapsed = time.monotonic() - tick_start
            sleep_time = self._frame_period - elapsed
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            else:
                await asyncio.sleep(0)

        logger.info("LookaheadScheduler stopped")

    async def _dispatch_all(self) -> None:
        now = time.monotonic()
        tasks: list[asyncio.Task[None]] = []

        for device in self._devices:
            if not device.adapter.is_connected:
                continue

            target_time = now + device.tracker.effective_latency_s
            frame = self._ring_buffer.find_nearest(target_time)

            if frame is None:
                logger.debug(
                    "No frame for '{}' (latency={:.0f}ms, buffer fill={:.0%})",
                    device.adapter.device_info.name,
                    device.tracker.effective_latency_ms,
                    self._ring_buffer.fill_level,
                )
                continue

            task = asyncio.create_task(self._send_to_device(device, frame.colors))
            tasks.append(task)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    @staticmethod
    async def _send_to_device(device: ManagedDevice, colors: object) -> None:
        try:
            await device.adapter.send_frame(colors)  # type: ignore[arg-type]
        except Exception:
            logger.exception(
                "Failed to send frame to '{}'",
                device.adapter.device_info.name,
            )
