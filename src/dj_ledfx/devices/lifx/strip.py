from __future__ import annotations

import struct
from typing import TYPE_CHECKING

import numpy as np
from loguru import logger
from numpy.typing import NDArray

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.lifx.packet import (
    LifxPacket,
    build_set_extended_color_zones,
    parse_state_extended_color_zones,
    rgb_array_to_hsbk,
)
from dj_ledfx.spatial.geometry import DeviceGeometry, StripGeometry
from dj_ledfx.types import DeviceInfo

if TYPE_CHECKING:
    from dj_ledfx.devices.lifx.transport import LifxTransport

MAX_ZONES_PER_PACKET = 82


class LifxStripAdapter(DeviceAdapter):
    supports_latency_probing = False

    def __init__(
        self,
        transport: LifxTransport,
        device_info: DeviceInfo,
        target_mac: bytes,
        zone_count: int = 1,
        kelvin: int = 3500,
    ) -> None:
        self._transport = transport
        self._device_info = device_info
        self._target_mac = target_mac
        self._zone_count = zone_count
        self._kelvin = kelvin
        self._is_connected = False
        self._addr = (device_info.address.split(":")[0], int(device_info.address.split(":")[1]))

    @property
    def device_info(self) -> DeviceInfo:
        return self._device_info

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def led_count(self) -> int:
        return self._zone_count

    @property
    def geometry(self) -> DeviceGeometry:
        return StripGeometry(direction=(1, 0, 0), length=1.0)

    def _make_packet(self, msg_type: int, payload: bytes, *, res_required: bool = False) -> LifxPacket:
        return LifxPacket(
            tagged=False,
            source=self._transport.source_id,
            target=self._target_mac + b"\x00\x00",
            ack_required=False,
            res_required=res_required,
            sequence=self._transport.next_sequence() % 256,
            msg_type=msg_type,
            payload=payload,
        )

    async def connect(self) -> None:
        self._is_connected = True

    async def disconnect(self) -> None:
        self._is_connected = False

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        hsbk = rgb_array_to_hsbk(colors, kelvin=self._kelvin)
        for chunk_start in range(0, len(hsbk), MAX_ZONES_PER_PACKET):
            chunk = hsbk[chunk_start : chunk_start + MAX_ZONES_PER_PACKET]
            count = len(chunk)
            hsbk_tuples: list[tuple[int, int, int, int]] = [
                (int(c[0]), int(c[1]), int(c[2]), int(c[3])) for c in chunk
            ]
            pkt = self._make_packet(
                510,
                build_set_extended_color_zones(0, 1, chunk_start, count, hsbk_tuples),
            )
            self._transport.send_packet(pkt, self._addr)

    async def capture_state(self) -> bytes:
        """Query strip zones via GetExtendedColorZones(511) → StateExtendedColorZones(512)."""
        pkt = self._make_packet(511, b"", res_required=True)
        response = await self._transport.request_response(pkt, self._addr, response_type=512)
        if response is not None:
            try:
                zone_count, _zone_index, colors = parse_state_extended_color_zones(response.payload)
                # Pack as: zone_count(u16) + HSBK tuples (4 x u16 each)
                data = struct.pack("<H", zone_count)
                for h, s, b, k in colors:
                    data += struct.pack("<4H", h, s, b, k)
                return data
            except Exception:
                logger.warning("Failed to parse zone state for '{}'", self._device_info.name)
        return await super().capture_state()

    async def restore_state(self, state: bytes) -> None:
        """Restore strip zones to captured HSBK state."""
        if len(state) >= 2:
            try:
                zone_count = struct.unpack("<H", state[:2])[0]
                hsbk_data = state[2:]
                if len(hsbk_data) >= zone_count * 8:
                    colors: list[tuple[int, int, int, int]] = []
                    for i in range(zone_count):
                        h, s, b, k = struct.unpack("<4H", hsbk_data[i * 8 : i * 8 + 8])
                        colors.append((h, s, b, k))
                    for chunk_start in range(0, len(colors), MAX_ZONES_PER_PACKET):
                        chunk = colors[chunk_start : chunk_start + MAX_ZONES_PER_PACKET]
                        pkt = self._make_packet(
                            510,
                            build_set_extended_color_zones(500, 1, chunk_start, len(chunk), chunk),
                        )
                        self._transport.send_packet(pkt, self._addr)
                    return
            except Exception:
                logger.warning("Failed to restore zone state for '{}'", self._device_info.name)
        await super().restore_state(state)
