"""DiscoveryOrchestrator — continuous background device discovery."""

from __future__ import annotations

import asyncio
from datetime import UTC
from typing import TYPE_CHECKING, Any

from loguru import logger

from dj_ledfx.config import AppConfig
from dj_ledfx.devices.backend import DeviceBackend, DiscoveredDevice
from dj_ledfx.devices.manager import DeviceManager
from dj_ledfx.events import (
    DeviceDiscoveredEvent,
    DeviceOnlineEvent,
    EventBus,
)

if TYPE_CHECKING:
    from dj_ledfx.devices.adapter import DeviceAdapter
    from dj_ledfx.persistence.state_db import StateDB


class DiscoveryOrchestrator:
    """Owns backend lifecycle and continuous periodic discovery."""

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
        self._task: asyncio.Task[None] | None = None

        # Instantiate backends once; filter by is_enabled
        self._backends: list[DeviceBackend] = []
        for cls in DeviceBackend._registry:
            backend = cls()
            if backend.is_enabled(config):
                self._backends.append(backend)

    async def connect_known_devices(self, device_rows: list[dict[str, Any]]) -> int:
        """Directly connect to known devices from DB without network scanning.

        Called once at startup before the background discovery loop, so that
        previously-seen devices come online immediately without waiting for
        a network broadcast.

        Returns the number of devices promoted from offline to online.
        """
        promoted = 0
        for backend in self._backends:
            try:
                discovered = await backend.connect_known(device_rows, self._config)
            except Exception:
                logger.exception("connect_known failed for {}", type(backend).__name__)
                continue

            for device in discovered:
                info = device.adapter.device_info
                stable_id = info.effective_id
                name = info.name

                existing = self._manager.get_by_stable_id(stable_id)
                if existing is not None and existing.status == "offline":
                    self._manager.promote_device(
                        stable_id,
                        device.adapter,
                        tracker=device.tracker,
                        max_fps=device.max_fps,
                    )
                    self._event_bus.emit(DeviceOnlineEvent(stable_id=stable_id, name=name))
                    promoted += 1
                    if self._state_db:
                        await self._persist_device(device.adapter)
                elif existing is None:
                    # Device not in manager yet — add it directly
                    self._manager.add_device(device.adapter, device.tracker, device.max_fps)
                    self._event_bus.emit(DeviceDiscoveredEvent(stable_id=stable_id, name=name))
                    promoted += 1
                    if self._state_db:
                        await self._persist_device(device.adapter)

        if promoted:
            logger.info("Fast reconnect: {} device(s) online immediately", promoted)
        return promoted

    async def run_scan(self) -> int:
        """Run a single discovery scan across all backends.

        Returns total new devices found. Each device fires an event via
        the on_found callback as soon as it responds — no batching.
        """
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

    async def run(self) -> None:
        """Continuous discovery loop: broadcast every N seconds, process responses instantly."""
        self._running = True
        interval = self._config.discovery.broadcast_interval_s
        logger.info("Discovery loop started (broadcast every {:.0f}s)", interval)

        while self._running:
            try:
                found = await self.run_scan()
                if found:
                    logger.info("Discovery scan: {} new device(s)", found)
            except Exception:
                logger.exception("Discovery scan failed")
            await asyncio.sleep(interval)

    def start(self) -> None:
        """Start the continuous discovery loop as a background task."""
        self._task = asyncio.create_task(self.run())

    async def _discover_backend(self, backend: DeviceBackend) -> int:
        """Discover devices from a single backend.

        Devices are promoted/added and events emitted via *on_found* as soon
        as each device is ready, rather than waiting for the full scan timeout.
        """
        new_count = 0
        persist_tasks: list[asyncio.Task[None]] = []

        def _on_found(device: DiscoveredDevice) -> None:
            nonlocal new_count
            info = device.adapter.device_info
            stable_id = info.effective_id
            name = info.name

            existing = self._manager.get_by_stable_id(stable_id)
            if existing is None:
                # Check by name as fallback (device may have had no stable_id before)
                existing_by_name = self._manager.get_device(name)
                if existing_by_name is None:
                    self._manager.add_device(device.adapter, device.tracker, device.max_fps)
                    self._event_bus.emit(DeviceDiscoveredEvent(stable_id=stable_id, name=name))
                    new_count += 1
                    if self._state_db:
                        persist_tasks.append(
                            asyncio.create_task(self._persist_device(device.adapter))
                        )
                elif existing_by_name.status == "offline":
                    # Promote the offline device using the freshly discovered adapter
                    self._manager.promote_device(
                        existing_by_name.adapter.device_info.effective_id,
                        device.adapter,
                        tracker=device.tracker,
                        max_fps=device.max_fps,
                    )
                    self._event_bus.emit(DeviceOnlineEvent(stable_id=stable_id, name=name))
                    new_count += 1
                    if self._state_db:
                        persist_tasks.append(
                            asyncio.create_task(self._persist_device(device.adapter))
                        )
                else:
                    logger.debug(
                        "Device '{}' already managed online under different stable_id, skipping",
                        name,
                    )
            elif existing.status == "offline":
                self._manager.promote_device(
                    stable_id,
                    device.adapter,
                    tracker=device.tracker,
                    max_fps=device.max_fps,
                )
                self._event_bus.emit(DeviceOnlineEvent(stable_id=stable_id, name=name))
                if self._state_db:
                    persist_tasks.append(asyncio.create_task(self._persist_device(device.adapter)))

        # Collect stable_ids of already-online devices so backends can skip them.
        # Offline (ghost) devices are intentionally excluded so they can be
        # rediscovered and promoted back online.
        skip_ids = {
            d.adapter.device_info.stable_id
            for d in self._manager.devices
            if d.adapter.device_info.stable_id and d.status == "online"
        }

        try:
            await backend.discover(self._config, on_found=_on_found, skip_ids=skip_ids)
        except Exception:
            logger.exception("Discovery failed for {}", type(backend).__name__)
            return 0

        # Wait for any still-pending persist writes
        if persist_tasks:
            await asyncio.gather(*persist_tasks, return_exceptions=True)

        return new_count

    async def _persist_device(self, adapter: DeviceAdapter) -> None:
        if not self._state_db:
            return
        from datetime import datetime

        info = adapter.device_info
        address = info.address or ""
        ip = address.split(":")[0] if ":" in address else address
        _record = getattr(adapter, "_record", None)
        await self._state_db.upsert_device(
            {
                "id": info.effective_id,
                "name": info.name,
                "backend": info.backend,
                "led_count": adapter.led_count,
                "ip": ip,
                "mac": getattr(info, "mac", None),
                "last_seen": datetime.now(UTC).isoformat(),
                "device_type": info.device_type,
                "device_id": _record.device_id if _record is not None else None,
                "sku": _record.sku if _record is not None else None,
            }
        )

    async def shutdown(self) -> None:
        """Cancel discovery loop and shut down all backends."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        for backend in self._backends:
            try:
                await backend.shutdown()
            except Exception:
                logger.exception("Backend shutdown failed for {}", type(backend).__name__)
        self._backends.clear()
