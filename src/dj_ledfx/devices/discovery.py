"""DiscoveryOrchestrator — continuous background device discovery."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from datetime import UTC
from typing import TYPE_CHECKING, Any

from loguru import logger

from dj_ledfx.config import AppConfig
from dj_ledfx.devices.backend import DeviceBackend, DiscoveredDevice
from dj_ledfx.devices.govee.output import OUTPUT_KEY, LampOutputReport, lamp_report, planned
from dj_ledfx.devices.manager import DeviceManager
from dj_ledfx.events import DeviceDiscoveredEvent, DeviceOnlineEvent, EventBus

if TYPE_CHECKING:
    from dj_ledfx.devices.adapter import DeviceAdapter
    from dj_ledfx.devices.govee.output import GoveeOutput
    from dj_ledfx.latency.tracker import LatencyTracker
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
        # One scan at a time: a Govee scan has one reply handler, so two at once would cut
        # each other short (POST /api/devices/scan beside the loop). A lamp's output change
        # holds it too, so it never races a scan's swap of the same lamp.
        self._scan_lock = asyncio.Lock()

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
        for device in await self._connect_rows(device_rows):
            if self._merge(device):
                promoted += 1
                await self._persist_device(device.adapter)

        if promoted:
            logger.info("Fast reconnect: {} device(s) online immediately", promoted)
        return promoted

    async def output_of(self, stable_id: str) -> LampOutputReport | None:
        """A Govee lamp's own output, and how it plays: as its adapter plays while it's
        online, else as a scan will set it up. None: no Govee lamp has that id."""
        row = await self._lamp_row(stable_id)
        return self._report(row) if row is not None else None

    async def set_output(self, stable_id: str, own: GoveeOutput) -> LampOutputReport | None:
        """Keep a Govee lamp's own output in its row and play it at once (the light-output
        plan's ruling 17). An online lamp is set up again from its row with no network: the
        light monitor still says whether it answers. One that's offline takes the output
        when a scan finds it. None: no Govee lamp has that id."""
        async with self._scan_lock:
            if self._state_db is None or await self._lamp_row(stable_id) is None:
                return None
            await self._state_db.set_device_extra(stable_id, OUTPUT_KEY, own.to_extra())
            row = await self._lamp_row(stable_id)
            if row is None:
                return None
            await self._play(row)
            return self._report(row)

    async def apply_outputs(self) -> None:
        """Play each online Govee lamp's output as its row now holds it, where that isn't
        how it plays: a restored backup's outputs apply at once."""
        if self._state_db is None:
            return
        async with self._scan_lock:
            for row in await self._state_db.load_devices():
                if row.get("backend") != "govee":
                    continue
                report = self._report(row)
                if report.online and report.plays != planned(row, self._segment_override):
                    await self._play(row)

    async def run_scan(self) -> int:
        """Run a single discovery scan across all backends.

        Returns total new devices found. Each device fires an event via
        the on_found callback as soon as it responds — no batching.
        """
        async with self._scan_lock:
            known = await self._state_db.load_devices() if self._state_db else []
            results = await asyncio.gather(
                *(self._discover_backend(b, known) for b in self._backends),
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

    async def _discover_backend(
        self, backend: DeviceBackend, known: Sequence[Mapping[str, Any]]
    ) -> int:
        """Discover devices from a single backend, given the known devices' rows.

        Devices are promoted/added and events emitted via *on_found* as soon
        as each device is ready, rather than waiting for the full scan timeout.
        """
        new_count = 0
        persist_tasks: list[asyncio.Task[None]] = []

        def _on_found(device: DiscoveredDevice) -> None:
            nonlocal new_count
            if self._merge(device):
                new_count += 1
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
            await backend.discover(
                self._config, on_found=_on_found, skip_ids=skip_ids, known=known
            )
        except Exception:
            logger.exception("Discovery failed for {}", type(backend).__name__)
            return 0

        # Wait for any still-pending persist writes
        if persist_tasks:
            await asyncio.gather(*persist_tasks, return_exceptions=True)

        return new_count

    async def _connect_rows(self, rows: list[dict[str, Any]]) -> list[DiscoveredDevice]:
        """Each backend's known lights, set up from their rows at once; a backend that
        fails is logged and skipped."""
        found: list[DiscoveredDevice] = []
        for backend in self._backends:
            try:
                found += await backend.connect_known(rows, self._config)
            except Exception:
                logger.exception("connect_known failed for {}", type(backend).__name__)
        return found

    @property
    def _segment_override(self) -> int | None:
        """The config's Govee segment count, as the lamps were set up with it."""
        return self._config.devices.govee.segment_override

    async def _lamp_row(self, stable_id: str) -> dict[str, Any] | None:
        """A Govee lamp's device row; None for any other id."""
        if self._state_db is None:
            return None
        row = await self._state_db.load_device(stable_id)
        return row if row is not None and row.get("backend") == "govee" else None

    def _report(self, row: Mapping[str, Any]) -> LampOutputReport:
        managed = self._manager.get_by_stable_id(row["id"])
        live = managed.adapter if managed is not None and managed.status == "online" else None
        return lamp_report(row, live, self._segment_override)

    async def _play(self, row: Mapping[str, Any]) -> None:
        """Set an online light up again from its row, with no network, so that it plays what
        the row holds. An offline one takes it when a scan finds it."""
        managed = self._manager.get_by_stable_id(row["id"])
        if managed is None or managed.status != "online":
            return
        device = self._rebuild(row, managed.tracker)
        if device is None:
            name = managed.adapter.device_info.name
            logger.warning("{} plays as it did until it's set up again", name)
            return
        self._promote(row["id"], device)
        await self._persist_device(device.adapter)

    def _rebuild(self, row: Mapping[str, Any], tracker: LatencyTracker) -> DiscoveredDevice | None:
        """A light set up again from its row by its backend, with no network."""
        for backend in self._backends:
            try:
                device = backend.rebuild(row, self._config, tracker)
            except Exception:
                logger.exception("Setting {} up again failed", row.get("id"))
                continue
            if device is not None:
                return device
        return None

    def _promote(self, managed_id: str, device: DiscoveredDevice) -> None:
        """Put a set-up device in place of a managed one, online, and say so: the zone
        manager prepares it again, and the light monitor counts its misses afresh."""
        self._manager.replace_adapter(managed_id, device)
        device.accepted()
        info = device.adapter.device_info
        self._event_bus.emit(DeviceOnlineEvent(stable_id=info.effective_id, name=info.name))

    def _merge(self, device: DiscoveredDevice) -> bool:
        """Take a found device in. True when it's new here or came back online.

        It's matched by stable id. Its name is a fallback only for a light whose id
        changed: exactly one managed device has that name, and it's offline. Otherwise a
        new id is a new light, even beside lights of the same name: the PC's four RAM
        sticks share one (spec §6.3, §6.6).
        """
        info = device.adapter.device_info
        stable_id, name = info.effective_id, info.name
        existing = self._manager.get_by_stable_id(stable_id)
        if existing is None:
            named = [d for d in self._manager.devices if d.adapter.device_info.name == name]
            if len(named) == 1 and named[0].status == "offline":
                existing = named[0]
        if existing is None:
            self._manager.add_device(device.adapter, device.tracker, device.max_fps)
            device.accepted()
            self._event_bus.emit(DeviceDiscoveredEvent(stable_id=stable_id, name=name))
            return True
        if existing.status != "offline":
            return False  # a duplicate: its tracker never gets the light's round trips
        self._promote(existing.adapter.device_info.effective_id, device)
        return True

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
