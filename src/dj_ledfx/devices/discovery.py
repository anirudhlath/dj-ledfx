"""DiscoveryOrchestrator — multi-wave device discovery."""

from __future__ import annotations

import asyncio
from datetime import UTC
from typing import TYPE_CHECKING

from loguru import logger

from dj_ledfx.config import AppConfig
from dj_ledfx.devices.backend import DeviceBackend
from dj_ledfx.devices.manager import DeviceManager
from dj_ledfx.events import (
    DeviceDiscoveredEvent,
    DeviceOnlineEvent,
    DiscoveryCompleteEvent,
    DiscoveryWaveCompleteEvent,
    EventBus,
)

if TYPE_CHECKING:
    from dj_ledfx.devices.adapter import DeviceAdapter
    from dj_ledfx.persistence.state_db import StateDB


class DiscoveryOrchestrator:
    """Owns backend lifecycle and multi-wave discovery logic."""

    def __init__(
        self,
        config: AppConfig,
        device_manager: DeviceManager,
        event_bus: EventBus,
        state_db: StateDB | None = None,
    ) -> None:
        self._config = config
        self._manager = device_manager
        self._event_bus = event_bus
        self._state_db = state_db
        self._running = False
        self._reconnect_task: asyncio.Task[None] | None = None

        # Instantiate backends once; filter by is_enabled
        self._backends: list[DeviceBackend] = []
        for cls in DeviceBackend._registry:
            backend = cls()
            if backend.is_enabled(config):
                self._backends.append(backend)

    async def run_discovery(self, waves: int | None = None) -> int:
        """Run multi-wave discovery. Returns total new devices found."""
        num_waves = waves if waves is not None else self._config.discovery.waves
        total_found = 0

        for wave_num in range(1, num_waves + 1):
            logger.info("Discovery wave {}/{}", wave_num, num_waves)
            found = await self._run_wave()
            total_found += found
            self._event_bus.emit(DiscoveryWaveCompleteEvent(wave=wave_num, devices_found=found))
            if wave_num < num_waves:
                await asyncio.sleep(self._config.discovery.wave_interval_s)

        self._event_bus.emit(DiscoveryCompleteEvent(total_devices=total_found))
        logger.info("Discovery complete: {} total devices", total_found)
        return total_found

    async def _run_wave(self) -> int:
        """Run one discovery wave across all backends."""
        results = await asyncio.gather(
            *(self._discover_backend(b) for b in self._backends),
            return_exceptions=True,
        )
        found = 0
        for result in results:
            if isinstance(result, Exception):
                logger.error("Backend discovery failed: {}", result)
                continue
            found += result  # type: ignore[operator]
        return found

    async def _discover_backend(self, backend: DeviceBackend) -> int:
        """Discover devices from a single backend."""
        try:
            discovered = await backend.discover(self._config)
        except Exception:
            logger.exception("Discovery failed for {}", type(backend).__name__)
            return 0

        new_count = 0
        for device in discovered:
            info = device.adapter.device_info
            stable_id = info.stable_id if info.stable_id else info.name
            name = info.name

            existing = self._manager.get_by_stable_id(stable_id)
            if existing is None:
                # Check by name as fallback
                existing_by_name = self._manager.get_device(name)
                if existing_by_name is None:
                    self._manager.add_device(device.adapter, device.tracker, device.max_fps)
                    self._event_bus.emit(DeviceDiscoveredEvent(stable_id=stable_id, name=name))
                    new_count += 1
                    if self._state_db:
                        await self._persist_device(device.adapter)
            elif existing.status == "offline":
                self._manager.promote_device(stable_id, device.adapter)
                self._event_bus.emit(DeviceOnlineEvent(stable_id=stable_id, name=name))
                if self._state_db:
                    await self._persist_device(device.adapter)

        return new_count

    async def _persist_device(self, adapter: DeviceAdapter) -> None:
        if not self._state_db:
            return
        from datetime import datetime

        info = adapter.device_info
        address = info.address or ""
        ip = address.split(":")[0] if ":" in address else address
        await self._state_db.upsert_device(
            {
                "id": info.stable_id or info.name,
                "name": info.name,
                "backend": info.device_type.split("_")[0] if info.device_type else "",
                "led_count": adapter.led_count,
                "ip": ip,
                "mac": getattr(info, "mac", None),
                "last_seen": datetime.now(UTC).isoformat(),
            }
        )

    async def start_reconnect_loop(self) -> None:
        """Start background reconnect loop for offline devices."""
        self._running = True
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        interval = self._config.discovery.reconnect_interval_s
        while self._running:
            await asyncio.sleep(interval)
            offline_count = sum(1 for d in self._manager.devices if d.status == "offline")
            if offline_count > 0:
                logger.debug("Reconnect loop: {} offline devices", offline_count)
                await self._run_wave()

    async def shutdown(self) -> None:
        """Cancel reconnect loop and shut down all backends."""
        self._running = False
        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
        for backend in self._backends:
            try:
                await backend.shutdown()
            except Exception:
                logger.exception("Backend shutdown failed for {}", type(backend).__name__)
        self._backends.clear()
