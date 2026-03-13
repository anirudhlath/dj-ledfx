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
        return config.openrgb_enabled

    async def discover(self, config: AppConfig) -> list[DiscoveredDevice]:
        discovered = await OpenRGBAdapter.discover(
            host=config.openrgb_host, port=config.openrgb_port
        )
        logger.info("Discovered {} OpenRGB devices", len(discovered))

        results: list[DiscoveredDevice] = []
        for i in range(len(discovered)):
            try:
                adapter = OpenRGBAdapter(
                    host=config.openrgb_host,
                    port=config.openrgb_port,
                    device_index=i,
                )
                await adapter.connect()

                heuristic_ms = estimate_device_latency_ms(adapter.device_info.name)
                strategy: StaticLatency | EMALatency | WindowedMeanLatency
                if config.openrgb_latency_strategy == "static":
                    strategy = StaticLatency(config.openrgb_latency_ms)
                elif config.openrgb_latency_strategy == "ema":
                    strategy = EMALatency(initial_value_ms=heuristic_ms)
                else:
                    strategy = WindowedMeanLatency(
                        window_size=config.openrgb_latency_window_size,
                        initial_value_ms=heuristic_ms,
                    )

                tracker = LatencyTracker(
                    strategy=strategy,
                    manual_offset_ms=config.openrgb_manual_offset_ms,
                )
                results.append(DiscoveredDevice(
                    adapter=adapter, tracker=tracker, max_fps=config.openrgb_max_fps,
                ))
            except Exception:
                logger.exception("Failed to connect to OpenRGB device {}", i)

        return results
