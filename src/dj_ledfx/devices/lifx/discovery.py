# src/dj_ledfx/devices/lifx/discovery.py
from __future__ import annotations

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
        return config.lifx_enabled

    async def discover(self, config: AppConfig) -> list[DiscoveredDevice]:
        self._transport = LifxTransport()
        await self._transport.open()

        records = await self._transport.discover(timeout_s=config.lifx_discovery_timeout_s)
        logger.info("LIFX discovery found {} devices", len(records))

        results: list[DiscoveredDevice] = []
        for record in records:
            adapter = await self._create_adapter(record, config)
            tracker = self._create_tracker(config)
            await adapter.connect()

            # Register for RTT probing
            self._transport.register_device(
                record,
                rtt_callback=lambda rtt, t=tracker: t.update(rtt),  # type: ignore[misc]
            )

            results.append(
                DiscoveredDevice(
                    adapter=adapter,
                    tracker=tracker,
                    max_fps=config.lifx_max_fps,
                )
            )

        # Start probing after all devices registered
        if results:
            self._transport.start_probing(interval_s=config.lifx_echo_probe_interval_s)

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
            info = DeviceInfo(f"LIFX Tile ({record.ip})", "lifx_tile", led_count, str_addr)
            adapter = LifxTileChainAdapter(
                self._transport,
                info,
                record.mac,
                tile_count=tile_count,
                kelvin=config.lifx_default_kelvin,
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
            info = DeviceInfo(f"LIFX Strip ({record.ip})", "lifx_strip", zone_count, str_addr)
            return LifxStripAdapter(
                self._transport,
                info,
                record.mac,
                zone_count=zone_count,
                kelvin=config.lifx_default_kelvin,
            )

        else:
            info = DeviceInfo(f"LIFX Bulb ({record.ip})", "lifx_bulb", 1, str_addr)
            return LifxBulbAdapter(
                self._transport,
                info,
                record.mac,
                kelvin=config.lifx_default_kelvin,
            )

    def _create_tracker(self, config: AppConfig) -> LatencyTracker:
        strategy: StaticLatency | EMALatency | WindowedMeanLatency
        if config.lifx_latency_strategy == "static":
            strategy = StaticLatency(config.lifx_latency_ms)
        elif config.lifx_latency_strategy == "ema":
            strategy = EMALatency(initial_value_ms=config.lifx_latency_ms)
        else:
            strategy = WindowedMeanLatency(
                window_size=config.lifx_latency_window_size,
                initial_value_ms=config.lifx_latency_ms,
            )
        return LatencyTracker(strategy=strategy, manual_offset_ms=config.lifx_manual_offset_ms)
