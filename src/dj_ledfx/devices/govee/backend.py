# src/dj_ledfx/devices/govee/backend.py
from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from loguru import logger

from dj_ledfx.config import AppConfig
from dj_ledfx.devices.backend import DeviceBackend, DiscoveredDevice
from dj_ledfx.devices.govee.segment import GoveeSegmentAdapter
from dj_ledfx.devices.govee.sku_registry import get_device_capability, get_segment_count
from dj_ledfx.devices.govee.solid import GoveeSolidAdapter
from dj_ledfx.devices.govee.transport import GoveeTransport
from dj_ledfx.devices.govee.types import GoveeDeviceRecord
from dj_ledfx.latency.strategies import EMALatency, StaticLatency, WindowedMeanLatency
from dj_ledfx.latency.tracker import LatencyTracker


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

                capability = get_device_capability(record.sku)
                segment_count = get_segment_count(
                    record.sku, config_override=govee.segment_override
                )

                if capability.is_rgbic and segment_count > 0:
                    adapter: GoveeSegmentAdapter | GoveeSolidAdapter = GoveeSegmentAdapter(
                        transport, record, num_segments=segment_count
                    )
                    logger.info(
                        "Govee {} at {} → segment adapter ({} segments)",
                        record.sku,
                        record.ip,
                        segment_count,
                    )
                else:
                    adapter = GoveeSolidAdapter(transport, record)
                    logger.info(
                        "Govee {} at {} → solid adapter",
                        record.sku,
                        record.ip,
                    )

                await adapter.connect()
                tracker = self._create_tracker(config)

                transport.register_device(
                    record,
                    rtt_callback=lambda rtt, t=tracker: t.update(rtt),  # type: ignore[misc]
                )

                device = DiscoveredDevice(
                    adapter=adapter,
                    tracker=tracker,
                    max_fps=govee.max_fps,
                )
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

        await self._transport.discover(
            timeout_s=govee.discovery_timeout_s,
            on_record=_on_record,
        )

        # Wait for any in-flight setup tasks that outlasted the scan timeout
        if setup_tasks:
            await asyncio.gather(*setup_tasks, return_exceptions=True)

        if not results:
            logger.info("No Govee devices found — ensure LAN control is enabled in Govee app")

        if results:
            self._transport.start_probing(interval_s=govee.probe_interval_s)

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

                capability = get_device_capability(sku)
                segment_count = get_segment_count(sku, config_override=govee_cfg.segment_override)

                adapter: GoveeSegmentAdapter | GoveeSolidAdapter
                if capability.is_rgbic and segment_count > 0:
                    adapter = GoveeSegmentAdapter(
                        self._transport, record, num_segments=segment_count
                    )
                else:
                    adapter = GoveeSolidAdapter(self._transport, record)

                await adapter.connect()
                tracker = self._create_tracker(config)

                self._transport.register_device(
                    record,
                    rtt_callback=lambda rtt, t=tracker: t.update(rtt),  # type: ignore[misc]
                )

                results.append(
                    DiscoveredDevice(
                        adapter=adapter,
                        tracker=tracker,
                        max_fps=govee_cfg.max_fps,
                    )
                )
                logger.info("Reconnected known Govee device '{}' at {}", name, ip)
            except Exception:
                logger.exception(
                    "Failed to reconnect known Govee device '{}'", row.get("name", "?")
                )

        if results:
            self._transport.start_probing(interval_s=govee_cfg.probe_interval_s)

        return results

    async def shutdown(self) -> None:
        if self._transport:
            self._transport.stop_probing()
            await self._transport.close()
            self._transport = None

    def _create_tracker(self, config: AppConfig) -> LatencyTracker:
        govee = config.devices.govee
        strategy: StaticLatency | EMALatency | WindowedMeanLatency
        if govee.latency_strategy == "static":
            strategy = StaticLatency(govee.latency_ms)
        elif govee.latency_strategy == "ema":
            strategy = EMALatency(initial_value_ms=govee.latency_ms)
        else:
            strategy = WindowedMeanLatency(
                window_size=govee.latency_window_size,
                initial_value_ms=govee.latency_ms,
            )
        return LatencyTracker(strategy=strategy, manual_offset_ms=govee.manual_offset_ms)
