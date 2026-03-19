# src/dj_ledfx/devices/govee/backend.py
from __future__ import annotations

from loguru import logger

from dj_ledfx.config import AppConfig
from dj_ledfx.devices.backend import DeviceBackend, DiscoveredDevice
from dj_ledfx.devices.govee.segment import GoveeSegmentAdapter
from dj_ledfx.devices.govee.sku_registry import get_device_capability, get_segment_count
from dj_ledfx.devices.govee.solid import GoveeSolidAdapter
from dj_ledfx.devices.govee.transport import GoveeTransport
from dj_ledfx.latency.strategies import EMALatency, StaticLatency, WindowedMeanLatency
from dj_ledfx.latency.tracker import LatencyTracker


class GoveeBackend(DeviceBackend):
    def __init__(self) -> None:
        self._transport: GoveeTransport | None = None

    def is_enabled(self, config: AppConfig) -> bool:
        return config.devices.govee.enabled

    async def discover(self, config: AppConfig) -> list[DiscoveredDevice]:
        govee = config.devices.govee
        self._transport = GoveeTransport()
        try:
            await self._transport.open()
        except OSError:
            logger.exception("Failed to open Govee transport (port 4002 in use?)")
            self._transport = None
            return []

        records = await self._transport.discover(timeout_s=govee.discovery_timeout_s)
        if not records:
            logger.info("No Govee devices found — ensure LAN control is enabled in Govee app")

        results: list[DiscoveredDevice] = []
        for record in records:
            try:
                capability = get_device_capability(record.sku)
                segment_count = get_segment_count(
                    record.sku, config_override=govee.segment_override
                )

                if capability.is_rgbic and segment_count > 0:
                    adapter: GoveeSegmentAdapter | GoveeSolidAdapter = GoveeSegmentAdapter(
                        self._transport, record, num_segments=segment_count
                    )
                    logger.info(
                        "Govee {} at {} → segment adapter ({} segments)",
                        record.sku,
                        record.ip,
                        segment_count,
                    )
                else:
                    adapter = GoveeSolidAdapter(self._transport, record)
                    logger.info(
                        "Govee {} at {} → solid adapter",
                        record.sku,
                        record.ip,
                    )

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
                        max_fps=govee.max_fps,
                    )
                )
            except Exception:
                logger.exception(
                    "Failed to set up Govee device {} (sku={})",
                    record.ip,
                    record.sku,
                )
                continue

        if results:
            self._transport.start_probing(interval_s=govee.probe_interval_s)

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
