from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import numpy as np
from loguru import logger

from dj_ledfx.config import AppConfig
from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.backend import DeviceBackend
from dj_ledfx.events import EventBus
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.types import DeviceGroup


@dataclass
class ManagedDevice:
    adapter: DeviceAdapter
    tracker: LatencyTracker
    max_fps: int = 60


class DeviceManager:
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._devices: list[ManagedDevice] = []
        self._groups: dict[str, DeviceGroup] = {}
        self._device_groups: dict[str, str] = {}  # device_name -> group_name

    @property
    def devices(self) -> list[ManagedDevice]:
        return list(self._devices)

    @property
    def max_led_count(self) -> int:
        if not self._devices:
            return 0
        return max(d.adapter.led_count for d in self._devices)

    def add_device(
        self,
        adapter: DeviceAdapter,
        tracker: LatencyTracker,
        max_fps: int = 60,
    ) -> None:
        self._devices.append(ManagedDevice(adapter=adapter, tracker=tracker, max_fps=max_fps))
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
                logger.exception("Failed to disconnect from '{}'", device.adapter.device_info.name)

    def get_device(self, name: str) -> ManagedDevice | None:
        for d in self._devices:
            if d.adapter.device_info.name == name:
                return d
        return None

    def create_group(self, name: str, color: str) -> DeviceGroup:
        group = DeviceGroup(name=name, color=color)
        self._groups[name] = group
        return group

    def delete_group(self, name: str) -> None:
        self._groups.pop(name, None)
        self._device_groups = {k: v for k, v in self._device_groups.items() if v != name}

    def get_groups(self) -> dict[str, DeviceGroup]:
        return dict(self._groups)

    def assign_to_group(self, device_name: str, group_name: str) -> None:
        if self.get_device(device_name) is None:
            raise KeyError(f"Device not found: {device_name}")
        if group_name not in self._groups:
            raise KeyError(f"Group not found: {group_name}")
        self._device_groups[device_name] = group_name

    def get_device_group(self, device_name: str) -> str | None:
        return self._device_groups.get(device_name)

    async def rediscover(self, config: AppConfig) -> list[str]:
        """Re-run device discovery, adding only newly found devices."""
        existing_names = {d.adapter.device_info.name for d in self._devices}
        await DeviceBackend.shutdown_all()
        discovered = await DeviceBackend.discover_all(config)
        new_names: list[str] = []
        for d in discovered:
            name = d.adapter.device_info.name
            if name not in existing_names:
                self.add_device(d.adapter, d.tracker, d.max_fps)
                new_names.append(name)
        return new_names

    async def identify_device(self, device_name: str, duration_s: float = 3.0) -> None:
        device = self.get_device(device_name)
        if device is None:
            raise KeyError(f"Device not found: {device_name}")
        if not device.adapter.is_connected:
            raise ConnectionError(f"Device not connected: {device_name}")
        white = np.full((device.adapter.led_count, 3), 255, dtype=np.uint8)
        black = np.zeros((device.adapter.led_count, 3), dtype=np.uint8)
        end = time.monotonic() + duration_s
        while time.monotonic() < end:
            try:
                await device.adapter.send_frame(white)
                await asyncio.sleep(0.3)
                await device.adapter.send_frame(black)
                await asyncio.sleep(0.3)
            except Exception:
                break
