from __future__ import annotations

from collections.abc import Callable
from typing import Any

from loguru import logger

from dj_ledfx.config import AppConfig
from dj_ledfx.devices.backend import DeviceBackend, DiscoveredDevice
from dj_ledfx.devices.heuristics import estimate_device_latency_ms
from dj_ledfx.devices.openrgb import OpenRGBAdapter
from dj_ledfx.latency.strategies import EMALatency, StaticLatency, WindowedMeanLatency
from dj_ledfx.latency.tracker import LatencyTracker


class OpenRGBBackend(DeviceBackend):
    def is_enabled(self, config: AppConfig) -> bool:
        return config.devices.openrgb.enabled

    async def discover(
        self,
        config: AppConfig,
        on_found: Callable[[DiscoveredDevice], Any] | None = None,
        skip_ids: set[str] | None = None,
    ) -> list[DiscoveredDevice]:
        orgb = config.devices.openrgb
        discovered = await OpenRGBAdapter.discover(host=orgb.host, port=orgb.port)
        logger.info("Discovered {} OpenRGB devices", len(discovered))

        results: list[DiscoveredDevice] = []
        for i in range(len(discovered)):
            stable_id = f"openrgb:{orgb.host}:{orgb.port}:{i}"
            if skip_ids and stable_id in skip_ids:
                continue
            try:
                adapter = OpenRGBAdapter(
                    host=orgb.host,
                    port=orgb.port,
                    device_index=i,
                )
                await adapter.connect()

                heuristic_ms = estimate_device_latency_ms(adapter.device_info.name)
                strategy: StaticLatency | EMALatency | WindowedMeanLatency
                if orgb.latency_strategy == "static":
                    strategy = StaticLatency(orgb.latency_ms)
                elif orgb.latency_strategy == "ema":
                    strategy = EMALatency(initial_value_ms=heuristic_ms)
                else:
                    strategy = WindowedMeanLatency(
                        window_size=orgb.latency_window_size,
                        initial_value_ms=heuristic_ms,
                    )

                tracker = LatencyTracker(
                    strategy=strategy,
                    manual_offset_ms=orgb.manual_offset_ms,
                )
                device = DiscoveredDevice(
                    adapter=adapter,
                    tracker=tracker,
                    max_fps=orgb.max_fps,
                )
                results.append(device)
                if on_found is not None:
                    on_found(device)
            except Exception:
                logger.exception("Failed to connect to OpenRGB device {}", i)

        return results

    async def connect_known(
        self, device_rows: list[dict[str, Any]], config: AppConfig
    ) -> list[DiscoveredDevice]:
        """Directly connect to known OpenRGB devices from DB without network scanning."""
        orgb_rows = [r for r in device_rows if r.get("backend") == "openrgb"]
        if not orgb_rows:
            return []

        orgb_cfg = config.devices.openrgb
        results: list[DiscoveredDevice] = []
        for row in orgb_rows:
            try:
                stable_id = row.get("id") or ""
                name = row.get("name") or stable_id
                # stable_id format: openrgb:host:port:index
                parts = stable_id.split(":")
                if len(parts) == 4 and parts[0] == "openrgb":
                    host = parts[1]
                    port = int(parts[2])
                    device_index = int(parts[3])
                else:
                    # Fall back to config values
                    host = orgb_cfg.host
                    port = orgb_cfg.port
                    device_index = 0

                adapter = OpenRGBAdapter(host=host, port=port, device_index=device_index)
                await adapter.connect()

                heuristic_ms = estimate_device_latency_ms(adapter.device_info.name)
                strategy: StaticLatency | EMALatency | WindowedMeanLatency
                if orgb_cfg.latency_strategy == "static":
                    strategy = StaticLatency(orgb_cfg.latency_ms)
                elif orgb_cfg.latency_strategy == "ema":
                    strategy = EMALatency(initial_value_ms=heuristic_ms)
                else:
                    strategy = WindowedMeanLatency(
                        window_size=orgb_cfg.latency_window_size,
                        initial_value_ms=heuristic_ms,
                    )

                tracker = LatencyTracker(
                    strategy=strategy,
                    manual_offset_ms=orgb_cfg.manual_offset_ms,
                )
                results.append(
                    DiscoveredDevice(
                        adapter=adapter,
                        tracker=tracker,
                        max_fps=orgb_cfg.max_fps,
                    )
                )
                logger.info("Reconnected known OpenRGB device '{}' at {}:{}", name, host, port)
            except Exception:
                logger.exception(
                    "Failed to reconnect known OpenRGB device '{}'", row.get("name", "?")
                )

        return results
