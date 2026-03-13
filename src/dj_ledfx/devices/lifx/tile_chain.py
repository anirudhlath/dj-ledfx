from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.lifx.packet import (
    LifxPacket,
    build_set_tile_state64,
    rgb_array_to_hsbk,
)
from dj_ledfx.devices.lifx.types import TileInfo
from dj_ledfx.types import DeviceInfo

if TYPE_CHECKING:
    from dj_ledfx.devices.lifx.transport import LifxTransport

PIXELS_PER_TILE = 64


class LifxTileChainAdapter(DeviceAdapter):
    supports_latency_probing = False

    def __init__(
        self,
        transport: LifxTransport,
        device_info: DeviceInfo,
        target_mac: bytes,
        tile_count: int = 5,
        kelvin: int = 3500,
    ) -> None:
        self._transport = transport
        self._device_info = device_info
        self._target_mac = target_mac
        self._tile_count = tile_count
        self._kelvin = kelvin
        self._is_connected = False
        self._tiles: list[TileInfo] = []
        self._addr = (device_info.address.split(":")[0], int(device_info.address.split(":")[1]))

    @property
    def device_info(self) -> DeviceInfo:
        return self._device_info

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def led_count(self) -> int:
        return self._tile_count * PIXELS_PER_TILE

    @property
    def tiles(self) -> list[TileInfo]:
        return self._tiles

    async def connect(self) -> None:
        self._is_connected = True

    async def disconnect(self) -> None:
        self._is_connected = False

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        hsbk = rgb_array_to_hsbk(colors, kelvin=self._kelvin)
        for tile_idx in range(self._tile_count):
            start = tile_idx * PIXELS_PER_TILE
            end = start + PIXELS_PER_TILE
            chunk = hsbk[start:end]
            hsbk_tuples: list[tuple[int, int, int, int]] = [
                (int(c[0]), int(c[1]), int(c[2]), int(c[3])) for c in chunk
            ]
            pkt = LifxPacket(
                tagged=False,
                source=self._transport.source_id,
                target=self._target_mac + b"\x00\x00",
                ack_required=False,
                res_required=False,
                sequence=self._transport.next_sequence() % 256,
                msg_type=715,
                payload=build_set_tile_state64(
                    tile_idx,
                    1,
                    0,
                    0,
                    8,
                    0,
                    hsbk_tuples,
                ),
            )
            self._transport.send_packet(pkt, self._addr)
