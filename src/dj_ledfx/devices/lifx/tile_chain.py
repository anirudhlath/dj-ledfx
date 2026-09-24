from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.devices.lifx.base import LifxAdapterBase, hsbk_from_json
from dj_ledfx.devices.lifx.packet import (
    GET_TILE_EFFECT,
    HSBK,
    SET_TILE_EFFECT,
    SET_TILE_STATE_64,
    STATE_TILE_EFFECT,
    TileEffectState,
    TileEffectType,
    build_get_tile_effect,
    build_set_tile_effect,
    build_set_tile_state64,
    parse_state_tile_effect,
    rgb_array_to_hsbk,
)
from dj_ledfx.devices.lifx.types import TileInfo
from dj_ledfx.spatial.geometry import MatrixGeometry, TileLayout
from dj_ledfx.types import DeviceInfo

if TYPE_CHECKING:
    from dj_ledfx.devices.lifx.transport import LifxTransport

PIXELS_PER_PACKET = 64
DEFAULT_TILE_SIZE = (8, 8)
PIXEL_PITCH_M = 0.03


class LifxTileChainAdapter(LifxAdapterBase):
    """Matrix lights: Tile, Candle, Tube, Spot, Path, Ceiling. Sized from StateDeviceChain."""

    _effect_key = "tile_effect"

    def __init__(
        self,
        transport: LifxTransport,
        device_info: DeviceInfo,
        target_mac: bytes,
        tile_count: int = 5,
        kelvin: int = 3500,
        *,
        tiles: Sequence[TileInfo] = (),
        caps: DeviceCapabilities | None = None,
    ) -> None:
        super().__init__(
            transport,
            device_info,
            target_mac,
            kelvin=kelvin,
            caps=caps or DeviceCapabilities(protocol="LIFX", matrix=True),
        )
        self._tiles: list[TileInfo] = list(tiles)
        self._tile_count = len(self._tiles) or tile_count

    @property
    def tiles(self) -> list[TileInfo]:
        return self._tiles

    def _tile_sizes(self) -> list[tuple[int, int]]:
        if self._tiles:
            return [(tile.width, tile.height) for tile in self._tiles]
        return [DEFAULT_TILE_SIZE] * self._tile_count

    @property
    def led_count(self) -> int:
        return sum(width * height for width, height in self._tile_sizes())

    @property
    def geometry(self) -> MatrixGeometry:
        layouts: list[TileLayout] = []
        for index, (width, height) in enumerate(self._tile_sizes()):
            if index < len(self._tiles):
                tile = self._tiles[index]
                offset = (
                    tile.user_x * width * PIXEL_PITCH_M,
                    tile.user_y * height * PIXEL_PITCH_M,
                )
            else:
                offset = (index * (width + 1) * PIXEL_PITCH_M, 0.0)
            layouts.append(TileLayout(offset[0], offset[1], width, height))
        return MatrixGeometry(tiles=tuple(layouts), pixel_pitch=PIXEL_PITCH_M)

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        hsbk = rgb_array_to_hsbk(colors, kelvin=self._kelvin)
        start = 0
        for tile_index, (width, height) in enumerate(self._tile_sizes()):
            rows_per_packet = max(1, PIXELS_PER_PACKET // width)
            for row in range(0, height, rows_per_packet):
                rows = min(rows_per_packet, height - row)
                chunk = hsbk[start + row * width : start + (row + rows) * width]
                values: list[HSBK] = [(int(c[0]), int(c[1]), int(c[2]), int(c[3])) for c in chunk]
                self._send(
                    SET_TILE_STATE_64,
                    build_set_tile_state64(tile_index, 1, 0, row, width, 0, values),
                )
            start += width * height

    async def start_tile_effect(
        self, effect: TileEffectType, speed_ms: int, palette: Sequence[HSBK] = ()
    ) -> None:
        await self._command(
            SET_TILE_EFFECT, build_set_tile_effect(effect, speed_ms, palette), STATE_TILE_EFFECT
        )

    async def tile_effect(self) -> TileEffectState | None:
        return await self._query(
            GET_TILE_EFFECT, build_get_tile_effect(), STATE_TILE_EFFECT, parse_state_tile_effect
        )

    async def _stop_effect(self) -> None:
        await self.start_tile_effect(TileEffectType.OFF, 0)

    async def _start_effect(self, saved: dict[str, Any]) -> None:
        await self.start_tile_effect(
            TileEffectType(int(saved["effect"])),
            int(saved["speed_ms"]),
            [hsbk_from_json(colour) for colour in saved["palette"]],
        )

    async def _capture_extra(self) -> dict[str, Any]:
        effect = await self.tile_effect()
        if effect is None or effect.effect == TileEffectType.OFF:
            return {}
        return {
            "tile_effect": {
                "effect": effect.effect,
                "speed_ms": effect.speed_ms,
                "palette": [list(colour) for colour in effect.palette],
            }
        }
