# src/dj_ledfx/devices/lifx/discovery.py
from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from loguru import logger

from dj_ledfx.config import AppConfig
from dj_ledfx.devices.backend import DeviceBackend, DiscoveredDevice
from dj_ledfx.devices.lifx.bulb import LifxBulbAdapter
from dj_ledfx.devices.lifx.strip import LifxStripAdapter
from dj_ledfx.devices.lifx.tile_chain import LifxTileChainAdapter
from dj_ledfx.devices.lifx.transport import LifxTransport
from dj_ledfx.devices.lifx.types import LifxDeviceRecord, TileInfo
from dj_ledfx.latency.strategies import EMALatency, StaticLatency, WindowedMeanLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.types import DeviceInfo

# Product IDs with matrix capability (tiles, candle)
MATRIX_PRODUCTS = {55, 57, 68, 70}
# Product IDs with extended linear zones (strip, beam, neon)
MULTIZONE_PRODUCTS = {31, 32, 38, 52, 70, 89, 90, 91, 94}


class LifxBackend(DeviceBackend):
    def __init__(self) -> None:
        self._transport: LifxTransport | None = None

    def is_enabled(self, config: AppConfig) -> bool:
        return config.devices.lifx.enabled

    async def discover(
        self,
        config: AppConfig,
        on_found: Callable[[DiscoveredDevice], Any] | None = None,
        skip_ids: set[str] | None = None,
    ) -> list[DiscoveredDevice]:
        lifx = config.devices.lifx
        # Reuse existing transport if already open (e.g. multi-wave discovery)
        if self._transport is None or not self._transport.is_open:
            self._transport = LifxTransport()
            await self._transport.open()

        results: list[DiscoveredDevice] = []
        setup_tasks: list[asyncio.Task[None]] = []
        transport = self._transport  # local ref for closure

        async def _setup_device(record: LifxDeviceRecord) -> None:
            try:
                stable_id = f"lifx:{record.mac.hex()}"
                if skip_ids and stable_id in skip_ids:
                    return

                adapter = await self._create_adapter(record, config)
                tracker = self._create_tracker(config)
                await adapter.connect()
            except Exception:
                logger.exception(
                    "Failed to set up LIFX device {} (product={})",
                    record.ip,
                    record.product,
                )
                return

            # Register for RTT probing
            transport.register_device(
                record,
                rtt_callback=lambda rtt, t=tracker: t.update(rtt),  # type: ignore[misc]
            )

            device = DiscoveredDevice(
                adapter=adapter,
                tracker=tracker,
                max_fps=lifx.max_fps,
            )
            results.append(device)
            if on_found is not None:
                on_found(device)

        def _on_record(record: LifxDeviceRecord) -> None:
            task = asyncio.create_task(_setup_device(record))
            setup_tasks.append(task)

        await self._transport.discover(
            timeout_s=lifx.discovery_timeout_s,
            on_record=_on_record,
        )

        # Wait for any in-flight setup tasks that outlasted the scan timeout
        if setup_tasks:
            await asyncio.gather(*setup_tasks, return_exceptions=True)

        logger.info("LIFX discovery found {} devices", len(results))

        # Start probing after all devices registered
        if results:
            self._transport.start_probing(interval_s=lifx.echo_probe_interval_s)

        return results

    async def connect_known(
        self, device_rows: list[dict[str, Any]], config: AppConfig
    ) -> list[DiscoveredDevice]:
        """Directly connect to known LIFX devices from DB without network scanning."""
        lifx_rows = [r for r in device_rows if r.get("backend") == "lifx"]
        if not lifx_rows:
            return []

        # Open transport if not already open
        if self._transport is None or not self._transport.is_open:
            self._transport = LifxTransport()
            await self._transport.open()

        lifx_cfg = config.devices.lifx
        results: list[DiscoveredDevice] = []
        for row in lifx_rows:
            try:
                ip = row.get("ip") or ""
                mac_hex = row.get("mac") or ""
                device_type = row.get("device_type") or "lifx_bulb"
                led_count = row.get("led_count") or 1
                name = row.get("name") or f"LIFX ({ip})"
                stable_id = row.get("id") or f"lifx:{mac_hex}"

                if not ip or not mac_hex:
                    logger.warning("Skipping known LIFX device '{}': missing ip or mac", name)
                    continue

                # MAC bytes: mac_hex is a 12-char hex string (no colons)
                mac_hex_clean = mac_hex.replace(":", "")
                target_mac = bytes.fromhex(mac_hex_clean)

                str_addr = f"{ip}:56700"
                info = DeviceInfo(
                    name=name,
                    device_type=device_type,
                    led_count=led_count,
                    address=str_addr,
                    mac=mac_hex,
                    stable_id=stable_id,
                    backend="lifx",
                )

                adapter: LifxBulbAdapter | LifxStripAdapter | LifxTileChainAdapter
                if device_type == "lifx_tile":
                    tile_count = max(1, led_count // 64)
                    adapter = LifxTileChainAdapter(
                        self._transport,
                        info,
                        target_mac,
                        tile_count=tile_count,
                        kelvin=lifx_cfg.default_kelvin,
                    )
                elif device_type == "lifx_strip":
                    adapter = LifxStripAdapter(
                        self._transport,
                        info,
                        target_mac,
                        zone_count=led_count,
                        kelvin=lifx_cfg.default_kelvin,
                    )
                else:
                    adapter = LifxBulbAdapter(
                        self._transport,
                        info,
                        target_mac,
                        kelvin=lifx_cfg.default_kelvin,
                    )

                await adapter.connect()

                last_latency = row.get("last_latency_ms") or 50.0
                tracker = LatencyTracker(strategy=StaticLatency(float(last_latency)))

                # Register for RTT probing
                mock_record = LifxDeviceRecord(
                    ip=ip,
                    port=56700,
                    mac=target_mac,
                    vendor=1,
                    product=0,
                )
                self._transport.register_device(
                    mock_record,
                    rtt_callback=lambda rtt, t=tracker: t.update(rtt),  # type: ignore[misc]
                )

                results.append(
                    DiscoveredDevice(
                        adapter=adapter,
                        tracker=tracker,
                        max_fps=lifx_cfg.max_fps,
                    )
                )
                logger.info("Reconnected known LIFX device '{}' at {}", name, ip)
            except Exception:
                logger.exception(
                    "Failed to reconnect known LIFX device '{}'", row.get("name", "?")
                )

        if results:
            self._transport.start_probing(interval_s=lifx_cfg.echo_probe_interval_s)

        return results

    async def shutdown(self) -> None:
        if self._transport:
            await self._transport.close()
            self._transport = None

    async def _create_adapter(
        self,
        record: LifxDeviceRecord,
        config: AppConfig,
    ) -> LifxBulbAdapter | LifxStripAdapter | LifxTileChainAdapter:
        from dj_ledfx.devices.lifx.packet import (
            LifxPacket,
            parse_state_device_chain,
            parse_state_extended_color_zones,
        )

        assert self._transport is not None
        addr = (record.ip, record.port)
        target = record.mac + b"\x00\x00"
        str_addr = f"{record.ip}:{record.port}"

        lifx = config.devices.lifx
        mac_hex = record.mac.hex()
        if record.product in MATRIX_PRODUCTS:
            pkt = LifxPacket(
                tagged=False,
                source=self._transport.source_id,
                target=target,
                ack_required=False,
                res_required=True,
                sequence=self._transport.next_sequence() % 256,
                msg_type=701,
                payload=b"",
            )
            resp = await self._transport.request_response(pkt, addr, response_type=702)
            tile_count = 5
            tiles: list[TileInfo] = []
            if resp:
                tiles = parse_state_device_chain(resp.payload)
                tile_count = len(tiles) if tiles else 5
            led_count = tile_count * 64
            info = DeviceInfo(
                f"LIFX Tile ({record.ip})",
                "lifx_tile",
                led_count,
                str_addr,
                mac=mac_hex,
                stable_id=f"lifx:{mac_hex}",
                backend="lifx",
            )
            adapter = LifxTileChainAdapter(
                self._transport,
                info,
                record.mac,
                tile_count=tile_count,
                kelvin=lifx.default_kelvin,
            )
            adapter._tiles = tiles
            return adapter

        elif record.product in MULTIZONE_PRODUCTS:
            pkt = LifxPacket(
                tagged=False,
                source=self._transport.source_id,
                target=target,
                ack_required=False,
                res_required=True,
                sequence=self._transport.next_sequence() % 256,
                msg_type=511,
                payload=b"",
            )
            resp = await self._transport.request_response(pkt, addr, response_type=512)
            zone_count = 1
            if resp:
                zone_count, _, _ = parse_state_extended_color_zones(resp.payload)
            info = DeviceInfo(
                f"LIFX Strip ({record.ip})",
                "lifx_strip",
                zone_count,
                str_addr,
                mac=mac_hex,
                stable_id=f"lifx:{mac_hex}",
                backend="lifx",
            )
            return LifxStripAdapter(
                self._transport,
                info,
                record.mac,
                zone_count=zone_count,
                kelvin=lifx.default_kelvin,
            )

        else:
            info = DeviceInfo(
                f"LIFX Bulb ({record.ip})",
                "lifx_bulb",
                1,
                str_addr,
                mac=mac_hex,
                stable_id=f"lifx:{mac_hex}",
                backend="lifx",
            )
            return LifxBulbAdapter(
                self._transport,
                info,
                record.mac,
                kelvin=lifx.default_kelvin,
            )

    def _create_tracker(self, config: AppConfig) -> LatencyTracker:
        lifx = config.devices.lifx
        strategy: StaticLatency | EMALatency | WindowedMeanLatency
        if lifx.latency_strategy == "static":
            strategy = StaticLatency(lifx.latency_ms)
        elif lifx.latency_strategy == "ema":
            strategy = EMALatency(initial_value_ms=lifx.latency_ms)
        else:
            strategy = WindowedMeanLatency(
                window_size=lifx.latency_window_size,
                initial_value_ms=lifx.latency_ms,
            )
        return LatencyTracker(strategy=strategy, manual_offset_ms=lifx.manual_offset_ms)
