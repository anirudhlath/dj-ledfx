from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, TypeVar

from loguru import logger

from dj_ledfx.config import AppConfig
from dj_ledfx.devices.backend import DeviceBackend, DiscoveredDevice
from dj_ledfx.devices.lifx.base import LifxAdapterBase
from dj_ledfx.devices.lifx.bulb import LifxBulbAdapter
from dj_ledfx.devices.lifx.packet import (
    GET_COLOR,
    GET_DEVICE_CHAIN,
    GET_EXTENDED_COLOR_ZONES,
    LIGHT_STATE,
    STATE_DEVICE_CHAIN,
    STATE_EXTENDED_COLOR_ZONES,
    parse_light_state,
    parse_state_device_chain,
    parse_state_extended_color_zones,
)
from dj_ledfx.devices.lifx.products import lifx_capabilities
from dj_ledfx.devices.lifx.strip import LifxStripAdapter
from dj_ledfx.devices.lifx.tile_chain import LifxTileChainAdapter, tile_sizes
from dj_ledfx.devices.lifx.transport import LifxTransport
from dj_ledfx.devices.lifx.types import LifxDeviceRecord, TileInfo
from dj_ledfx.latency.strategies import EMALatency, StaticLatency, WindowedMeanLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.types import DeviceInfo

LIFX_PORT = 56700

T = TypeVar("T")


def _label_of(payload: bytes) -> str:
    *_colour, label = parse_light_state(payload)
    return label.strip()


def _zone_count_of(payload: bytes) -> int:
    zone_count, _index, _colours = parse_state_extended_color_zones(payload)
    return zone_count


class LifxBackend(DeviceBackend):
    def __init__(self) -> None:
        self._transport: LifxTransport | None = None
        self._names: dict[str, str] = {}  # name -> stable_id, so two lights never share one

    def is_enabled(self, config: AppConfig) -> bool:
        return config.devices.lifx.enabled

    async def _open_transport(self) -> LifxTransport:
        if self._transport is None or not self._transport.is_open:
            self._transport = LifxTransport()
            await self._transport.open()
        return self._transport

    async def discover(
        self,
        config: AppConfig,
        on_found: Callable[[DiscoveredDevice], Any] | None = None,
        skip_ids: set[str] | None = None,
    ) -> list[DiscoveredDevice]:
        lifx = config.devices.lifx
        transport = await self._open_transport()
        results: list[DiscoveredDevice] = []
        setup_tasks: list[asyncio.Task[None]] = []

        async def _setup_device(record: LifxDeviceRecord) -> None:
            if skip_ids and f"lifx:{record.mac.hex()}" in skip_ids:
                return
            try:
                device = await self._setup(record, config)
            except Exception:
                logger.exception(
                    "Failed to set up LIFX device {} (product={})", record.ip, record.product
                )
                return
            if device is None:
                return
            results.append(device)
            if on_found is not None:
                on_found(device)

        def _on_record(record: LifxDeviceRecord) -> None:
            setup_tasks.append(asyncio.create_task(_setup_device(record)))

        await transport.discover(timeout_s=lifx.discovery_timeout_s, on_record=_on_record)
        if setup_tasks:
            await asyncio.gather(*setup_tasks, return_exceptions=True)

        logger.info("LIFX discovery found {} devices", len(results))
        if results:
            transport.start_probing(interval_s=lifx.echo_probe_interval_s)
        return results

    async def connect_known(
        self, device_rows: list[dict[str, Any]], config: AppConfig
    ) -> list[DiscoveredDevice]:
        """Reconnect known LIFX lights by asking each one what it is.

        A light that doesn't answer stays a ghost until discovery finds it.
        """
        rows = [row for row in device_rows if row.get("backend") == "lifx"]
        if not rows:
            return []
        transport = await self._open_transport()

        async def _reconnect(row: dict[str, Any]) -> DiscoveredDevice | None:
            ip = row.get("ip") or ""
            mac_hex = (row.get("mac") or "").replace(":", "")
            if not ip or not mac_hex:
                logger.warning(
                    "Skipping known LIFX device '{}': missing ip or mac", row.get("name")
                )
                return None
            mac = bytes.fromhex(mac_hex)
            version = await transport.query_version(mac, ip, LIFX_PORT)
            if version is None:
                logger.info(
                    "Known LIFX device '{}' didn't answer; it stays offline", row.get("name")
                )
                return None
            vendor, product = version
            record = LifxDeviceRecord(
                mac=mac, ip=ip, port=LIFX_PORT, vendor=vendor, product=product
            )
            return await self._setup(record, config)

        outcomes = await asyncio.gather(*(_reconnect(row) for row in rows), return_exceptions=True)
        results: list[DiscoveredDevice] = []
        for row, outcome in zip(rows, outcomes, strict=True):
            if isinstance(outcome, BaseException):
                logger.opt(exception=outcome).error(
                    "Failed to reconnect known LIFX device '{}'", row.get("name", "?")
                )
            elif outcome is not None:
                logger.info("Reconnected known LIFX device '{}'", outcome.adapter.device_info.name)
                results.append(outcome)
        if results:
            transport.start_probing(interval_s=config.devices.lifx.echo_probe_interval_s)
        return results

    async def shutdown(self) -> None:
        if self._transport:
            await self._transport.close()
            self._transport = None

    async def _setup(self, record: LifxDeviceRecord, config: AppConfig) -> DiscoveredDevice | None:
        assert self._transport is not None
        adapter = await self._create_adapter(record, config)
        if adapter is None:
            return None
        tracker = self._create_tracker(config)
        await adapter.connect()
        self._transport.register_device(
            record,
            rtt_callback=lambda rtt, t=tracker: t.update(rtt),  # type: ignore[misc]
        )
        return DiscoveredDevice(
            adapter=adapter, tracker=tracker, max_fps=config.devices.lifx.max_fps
        )

    async def _create_adapter(
        self, record: LifxDeviceRecord, config: AppConfig
    ) -> LifxAdapterBase | None:
        assert self._transport is not None
        transport = self._transport
        firmware = await transport.query_host_firmware(record.mac, record.ip, record.port)
        caps, relays = lifx_capabilities(record.product, firmware, record.vendor)
        if relays:
            logger.debug("Skipping LIFX switch {} ({})", record.ip, caps.model)
            return None
        stable_id = f"lifx:{record.mac.hex()}"
        label = await self._query_label(record)
        name = self._unique_name(label or f"{caps.model} ({record.ip})", stable_id)
        kelvin = config.devices.lifx.default_kelvin

        def _info(device_type: str, led_count: int) -> DeviceInfo:
            return DeviceInfo(
                name,
                device_type,
                led_count,
                f"{record.ip}:{record.port}",
                mac=record.mac.hex(),
                stable_id=stable_id,
                backend="lifx",
            )

        if caps.matrix:
            tiles = await self._query_chain(record)
            if not tiles:
                logger.warning("LIFX '{}' didn't report its matrix size; assuming 8x8 tiles", name)
            sizes = tile_sizes(tiles, 5 if caps.chain else 1)
            led_count = sum(width * height for width, height in sizes)
            return LifxTileChainAdapter(
                transport,
                _info("lifx_tile", led_count),
                record.mac,
                tile_count=len(sizes),
                kelvin=kelvin,
                tiles=tiles,
                caps=caps,
            )
        if caps.multizone and caps.extended_multizone:
            zones = await self._query_zone_count(record)
            return LifxStripAdapter(
                transport,
                _info("lifx_strip", zones),
                record.mac,
                zone_count=zones,
                kelvin=kelvin,
                caps=caps,
            )
        if caps.multizone:
            logger.info("LIFX '{}' has no extended multizone; it plays as one colour", name)
        return LifxBulbAdapter(
            transport, _info("lifx_bulb", 1), record.mac, kelvin=kelvin, caps=caps
        )

    def _unique_name(self, wanted: str, stable_id: str) -> str:
        owner = self._names.setdefault(wanted, stable_id)
        if owner == stable_id:
            return wanted
        name = f"{wanted} ({stable_id[-4:]})"
        self._names[name] = stable_id
        return name

    async def _query(
        self,
        record: LifxDeviceRecord,
        msg_type: int,
        reply_type: int,
        parse: Callable[[bytes], T],
        timeout: float,
    ) -> T | None:
        assert self._transport is not None
        return await self._transport.query(
            record.mac, (record.ip, record.port), msg_type, b"", reply_type, parse, timeout=timeout
        )

    async def _query_label(self, record: LifxDeviceRecord) -> str | None:
        label = await self._query(record, GET_COLOR, LIGHT_STATE, _label_of, 0.5)
        return label or None

    async def _query_chain(self, record: LifxDeviceRecord) -> list[TileInfo]:
        tiles = await self._query(
            record, GET_DEVICE_CHAIN, STATE_DEVICE_CHAIN, parse_state_device_chain, 1.0
        )
        return tiles or []

    async def _query_zone_count(self, record: LifxDeviceRecord) -> int:
        count = await self._query(
            record, GET_EXTENDED_COLOR_ZONES, STATE_EXTENDED_COLOR_ZONES, _zone_count_of, 1.0
        )
        if count is None:
            logger.warning("LIFX {} didn't report its zone count; assuming 1", record.ip)
            return 1
        return max(1, count)

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
