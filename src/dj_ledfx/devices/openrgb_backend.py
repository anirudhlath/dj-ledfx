from __future__ import annotations

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

    async def discover(self, config: AppConfig) -> list[DiscoveredDevice]:
        orgb = config.devices.openrgb
        discovered = await OpenRGBAdapter.discover(host=orgb.host, port=orgb.port)
        logger.info("Discovered {} OpenRGB devices", len(discovered))

        results: list[DiscoveredDevice] = []
        for i in range(len(discovered)):
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
                results.append(
                    DiscoveredDevice(
                        adapter=adapter,
                        tracker=tracker,
                        max_fps=orgb.max_fps,
                    )
                )
            except Exception:
                logger.exception("Failed to connect to OpenRGB device {}", i)

        return results
