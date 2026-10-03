# src/dj_ledfx/devices/govee/backend.py
from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from functools import partial
from typing import Any

from loguru import logger

from dj_ledfx.config import AppConfig
from dj_ledfx.devices.backend import DeviceBackend, DiscoveredDevice, configured_fps
from dj_ledfx.devices.govee.adapter_base import GoveeAdapterBase
from dj_ledfx.devices.govee.colour import GoveeColourAdapter
from dj_ledfx.devices.govee.output import GoveeOutput, lamp_plan
from dj_ledfx.devices.govee.razer import GoveeRazerAdapter
from dj_ledfx.devices.govee.sku_registry import get_device_capability
from dj_ledfx.devices.govee.transport import GoveeTransport
from dj_ledfx.devices.govee.types import GoveeDeviceRecord
from dj_ledfx.latency.tracker import LatencyTracker, tracker_for


def _record_of(row: Mapping[str, Any]) -> GoveeDeviceRecord | None:
    """A known lamp's record from its device row; None without an address."""
    ip = row.get("ip") or ""
    device_id = row.get("device_id") or ""
    if not device_id:  # from its stable id, "govee:{device_id}"
        device_id = (row.get("id") or "").removeprefix("govee:")
    if not ip:
        return None
    return GoveeDeviceRecord(
        ip=ip, device_id=device_id, sku=row.get("sku") or "", wifi_version="", ble_version=""
    )


class GoveeBackend(DeviceBackend):
    def __init__(self) -> None:
        self._transport: GoveeTransport | None = None

    def is_enabled(self, config: AppConfig) -> bool:
        return config.devices.govee.enabled

    async def discover(
        self,
        config: AppConfig,
        on_found: Callable[[DiscoveredDevice], Any] | None = None,
        skip_ids: set[str] | None = None,
        known: Sequence[Mapping[str, Any]] = (),
    ) -> list[DiscoveredDevice]:
        """A lamp found is set up playing its own output, from its row in *known*; a lamp
        with no row plays as the config and the SKU table say."""
        govee = config.devices.govee
        outputs = {
            row["id"]: GoveeOutput.from_extra(row.get("extra"))
            for row in known
            if row.get("backend") == "govee"
        }
        # Reuse existing transport if already open (e.g. multi-wave discovery)
        if self._transport is None or not self._transport.is_open:
            self._transport = GoveeTransport()
            try:
                await self._transport.open()
            except OSError:
                logger.exception("Failed to open Govee transport (port 4002 in use?)")
                self._transport = None
                return []

        results: list[DiscoveredDevice] = []
        setup_tasks: list[asyncio.Task[None]] = []

        transport = self._transport  # local ref for closure

        async def _setup_device(record: GoveeDeviceRecord) -> None:
            stable_id = f"govee:{record.device_id}"
            if skip_ids and stable_id in skip_ids:
                return
            output = outputs.get(stable_id, GoveeOutput())
            try:
                device = await self._setup(transport, record, config, output)
            except ConnectionError as silent:
                logger.warning("{}: a later scan tries it again", silent)
                return
            except Exception:
                logger.exception(
                    "Failed to set up Govee device {} (sku={})",
                    record.ip,
                    record.sku,
                )
                return
            results.append(device)
            if on_found is not None:
                on_found(device)

        def _on_record(record: GoveeDeviceRecord) -> None:
            task = asyncio.create_task(_setup_device(record))
            setup_tasks.append(task)

        await transport.discover(
            timeout_s=govee.discovery_timeout_s,
            on_record=_on_record,
        )

        # Wait for any in-flight setup tasks that outlasted the scan timeout
        if setup_tasks:
            await asyncio.gather(*setup_tasks, return_exceptions=True)

        if not results:
            logger.info("No Govee devices found — ensure LAN control is enabled in Govee app")

        return results

    async def connect_known(
        self, device_rows: list[dict[str, Any]], config: AppConfig
    ) -> list[DiscoveredDevice]:
        """Directly connect to known Govee devices from DB without network scanning."""
        govee_rows = [r for r in device_rows if r.get("backend") == "govee"]
        if not govee_rows:
            return []

        # Open transport if not already open
        if self._transport is None or not self._transport.is_open:
            self._transport = GoveeTransport()
            try:
                await self._transport.open()
            except OSError:
                logger.exception("Failed to open Govee transport (port 4002 in use?)")
                self._transport = None
                return []
        transport = self._transport

        results: list[DiscoveredDevice] = []
        for row in govee_rows:
            name = row.get("name") or f"Govee ({row.get('ip') or '?'})"
            record = _record_of(row)
            if record is None:
                logger.warning("Skipping known Govee device '{}': missing ip", name)
                continue
            output = GoveeOutput.from_extra(row.get("extra"))
            try:
                results.append(await self._setup(transport, record, config, output))
            except ConnectionError:
                logger.warning("Known Govee lamp '{}' didn't answer; it stays offline", name)
                continue
            except Exception:
                logger.exception("Failed to reconnect known Govee device '{}'", name)
                continue
            logger.info("Reconnected known Govee device '{}' at {}", name, record.ip)

        return results

    def rebuild(
        self, row: Mapping[str, Any], config: AppConfig, tracker: LatencyTracker
    ) -> DiscoveredDevice | None:
        """An online lamp set up again from its row, playing its own output as the row now
        holds it. No network: it's connected as the adapter it replaces was, and the light
        monitor still says whether it answers. Its tracker keeps the lamp's round trips."""
        record = _record_of(row) if row.get("backend") == "govee" else None
        if record is None or self._transport is None:
            return None
        output = GoveeOutput.from_extra(row.get("extra"))
        adapter = self._adapter(self._transport, record, config, output, connected=True)
        return DiscoveredDevice(adapter=adapter, tracker=tracker, max_fps=adapter.stream_fps)

    async def shutdown(self) -> None:
        if self._transport:
            await self._transport.close()
            self._transport = None

    async def _setup(
        self,
        transport: GoveeTransport,
        record: GoveeDeviceRecord,
        config: AppConfig,
        output: GoveeOutput,
    ) -> DiscoveredDevice:
        """Connect a lamp as its plan says it plays; once the orchestrator takes it in, its
        status reads time its round trips. Raises ConnectionError when it doesn't answer."""
        adapter = self._adapter(transport, record, config, output)
        await adapter.connect()
        tracker = tracker_for(config.devices.govee, display_ms=adapter.display_ms)
        return DiscoveredDevice(
            adapter=adapter,
            tracker=tracker,
            max_fps=adapter.stream_fps,
            on_accepted=partial(transport.register_device, record, tracker.update_rtt),
        )

    def _adapter(
        self,
        transport: GoveeTransport,
        record: GoveeDeviceRecord,
        config: AppConfig,
        output: GoveeOutput,
        *,
        connected: bool = False,
    ) -> GoveeAdapterBase:
        """The adapter a lamp plays through, as its plan says (razer, or one colour on any
        number of segments), built at the configured rate: a colour adapter caps its own."""
        govee = config.devices.govee
        capability = get_device_capability(record.sku)
        plan = lamp_plan(capability, output, govee.segment_override)
        kind: type[GoveeAdapterBase] = GoveeRazerAdapter if plan.razer else GoveeColourAdapter
        adapter = kind(
            transport,
            record,
            plan.segments,
            form=capability.form,
            from_top=capability.segments_from_top,
            connected=connected,
            max_fps=configured_fps(config, govee.max_fps),
        )
        logger.info(
            "Govee {} at {}: {} segment(s), {}, {} frames a second",
            record.sku,
            record.ip,
            plan.segments,
            "razer" if plan.razer else "one colour",
            adapter.stream_fps,
        )
        return adapter
