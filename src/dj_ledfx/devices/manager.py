from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.events import EventBus
from dj_ledfx.latency.tracker import LatencyTracker


@dataclass
class ManagedDevice:
    adapter: DeviceAdapter
    tracker: LatencyTracker


class DeviceManager:
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._devices: list[ManagedDevice] = []

    @property
    def devices(self) -> list[ManagedDevice]:
        return list(self._devices)

    @property
    def max_led_count(self) -> int:
        if not self._devices:
            return 0
        return max(d.adapter.led_count for d in self._devices)

    def add_device(self, adapter: DeviceAdapter, tracker: LatencyTracker) -> None:
        self._devices.append(ManagedDevice(adapter=adapter, tracker=tracker))
        logger.info(
            "Added device '{}' ({} LEDs, latency={:.0f}ms)",
            adapter.device_info.name,
            adapter.led_count,
            tracker.effective_latency_ms,
        )

    async def connect_all(self) -> None:
        for device in self._devices:
            try:
                await device.adapter.connect()
            except Exception:
                logger.exception("Failed to connect to '{}'", device.adapter.device_info.name)

    async def disconnect_all(self) -> None:
        for device in self._devices:
            try:
                await device.adapter.disconnect()
            except Exception:
                logger.exception(
                    "Failed to disconnect from '{}'", device.adapter.device_info.name
                )
