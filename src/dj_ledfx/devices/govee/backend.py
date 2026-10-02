# src/dj_ledfx/devices/govee/backend.py
from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from loguru import logger

from dj_ledfx.config import AppConfig
from dj_ledfx.devices.backend import DeviceBackend, DiscoveredDevice
from dj_ledfx.devices.govee.adapter_base import GoveeAdapterBase
from dj_ledfx.devices.govee.output import GoveeOutput, lamp_fps, lamp_plan
from dj_ledfx.devices.govee.segment import GoveeSegmentAdapter
from dj_ledfx.devices.govee.sku_registry import get_device_capability
from dj_ledfx.devices.govee.solid import GoveeSolidAdapter
from dj_ledfx.devices.govee.transport import GoveeTransport
from dj_ledfx.devices.govee.types import GoveeDeviceRecord
from dj_ledfx.latency.strategies import make_strategy
from dj_ledfx.latency.tracker import LatencyTracker


class GoveeBackend(DeviceBackend):
    def __init__(self) -> None:
        self._transport: GoveeTransport | None = None
        self._outputs: dict[str, GoveeOutput] = {}  # each known lamp's own, by stable id

    def is_enabled(self, config: AppConfig) -> bool:
        return config.devices.govee.enabled

    async def discover(
        self,
        config: AppConfig,
        on_found: Callable[[DiscoveredDevice], Any] | None = None,
        skip_ids: set[str] | None = None,
    ) -> list[DiscoveredDevice]:
        govee = config.devices.govee
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
            try:
                stable_id = f"govee:{record.device_id}"
                if skip_ids and stable_id in skip_ids:
                    return
                device = await self._setup(transport, record, config)
                results.append(device)
                if on_found is not None:
                    on_found(device)
            except Exception:
                logger.exception(
                    "Failed to set up Govee device {} (sku={})",
                    record.ip,
                    record.sku,
                )

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

        if results:
            transport.start_probing(interval_s=govee.probe_interval_s)

        return results

    async def connect_known(
        self, device_rows: list[dict[str, Any]], config: AppConfig
    ) -> list[DiscoveredDevice]:
        """Directly connect to known Govee devices from DB without network scanning."""
        govee_rows = [r for r in device_rows if r.get("backend") == "govee"]
        if not govee_rows:
            return []

        govee_cfg = config.devices.govee

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
            try:
                ip = row.get("ip") or ""
                device_id = row.get("device_id") or ""
                sku = row.get("sku") or ""
                # Fallback: extract device_id from stable_id (format: "govee:{device_id}")
                if not device_id:
                    stable_id = row.get("id") or ""
                    if stable_id.startswith("govee:"):
                        device_id = stable_id[len("govee:") :]
                # Its own output: for now, and for the scan that finds it if it doesn't
                # answer now (the light-output plan's ruling 17)
                self._outputs[f"govee:{device_id}"] = GoveeOutput.from_extra(row.get("extra"))
                name = row.get("name") or f"Govee ({ip})"

                if not ip:
                    logger.warning("Skipping known Govee device '{}': missing ip", name)
                    continue

                record = GoveeDeviceRecord(
                    ip=ip,
                    device_id=device_id,
                    sku=sku,
                    wifi_version="",
                    ble_version="",
                )
                results.append(await self._setup(transport, record, config))
                logger.info("Reconnected known Govee device '{}' at {}", name, ip)
            except Exception:
                logger.exception(
                    "Failed to reconnect known Govee device '{}'", row.get("name", "?")
                )

        if results:
            transport.start_probing(interval_s=govee_cfg.probe_interval_s)

        return results

    async def shutdown(self) -> None:
        if self._transport:
            self._transport.stop_probing()
            await self._transport.close()
            self._transport = None

    async def _setup(
        self, transport: GoveeTransport, record: GoveeDeviceRecord, config: AppConfig
    ) -> DiscoveredDevice:
        """Connect a lamp as its plan says it plays, and register it for latency probes.
        Raises ConnectionError when it doesn't answer."""
        adapter, max_fps = self._adapter(transport, record, config)
        await adapter.connect()
        tracker = self._create_tracker(config)
        transport.register_device(record, rtt_callback=tracker.update_rtt)
        return DiscoveredDevice(adapter=adapter, tracker=tracker, max_fps=max_fps)

    def _adapter(
        self, transport: GoveeTransport, record: GoveeDeviceRecord, config: AppConfig
    ) -> tuple[GoveeAdapterBase, int]:
        """The adapter a lamp plays through, and its rate: razer segments, one colour across
        its segments, or one colour on a lamp with fewer than two."""
        govee = config.devices.govee
        capability = get_device_capability(record.sku)
        output = self._outputs.get(f"govee:{record.device_id}", GoveeOutput())
        plan = lamp_plan(capability, output, govee.segment_override)
        adapter: GoveeAdapterBase
        if plan.segments < 2:
            adapter = GoveeSolidAdapter(transport, record)
        else:
            adapter = GoveeSegmentAdapter(
                transport,
                record,
                plan.segments,
                razer=plan.razer,
                form=capability.form,
                from_top=capability.segments_from_top,
            )
        max_fps = lamp_fps(plan, govee.max_fps)
        logger.info(
            "Govee {} at {}: {} segment(s), {}, {} frames a second",
            record.sku,
            record.ip,
            plan.segments,
            "razer" if plan.razer else "one colour",
            max_fps,
        )
        return adapter, max_fps

    def _create_tracker(self, config: AppConfig) -> LatencyTracker:
        govee = config.devices.govee
        strategy = make_strategy(
            govee.latency_strategy, govee.latency_ms, govee.latency_window_size
        )
        return LatencyTracker(strategy, govee.manual_offset_ms)
