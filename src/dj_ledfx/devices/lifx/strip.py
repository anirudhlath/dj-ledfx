from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import numpy as np
from loguru import logger
from numpy.typing import NDArray

from dj_ledfx.devices.capabilities import DeviceCapabilities, FirmwareRejected, NoAnswer
from dj_ledfx.devices.lifx.base import RESTORE_FADE_MS, LifxAdapterBase, hsbk_from_json
from dj_ledfx.devices.lifx.packet import (
    GET_EXTENDED_COLOR_ZONES,
    GET_MULTIZONE_EFFECT,
    HSBK,
    SET_EXTENDED_COLOR_ZONES,
    SET_MULTIZONE_EFFECT,
    STATE_EXTENDED_COLOR_ZONES,
    STATE_MULTIZONE_EFFECT,
    MultiZoneEffectState,
    MultiZoneEffectType,
    build_set_extended_color_zones,
    build_set_multizone_effect,
    parse_state_extended_color_zones,
    parse_state_multizone_effect,
    rgb_array_to_hsbk,
)
from dj_ledfx.spatial.geometry import DeviceGeometry, StripGeometry
from dj_ledfx.types import DeviceInfo

if TYPE_CHECKING:
    from dj_ledfx.devices.lifx.transport import LifxTransport

MAX_ZONES_PER_PACKET = 82


def _colours_of_zones(payload: bytes) -> list[HSBK]:
    _count, _index, colours = parse_state_extended_color_zones(payload)
    return colours


class LifxStripAdapter(LifxAdapterBase):
    """Extended-multizone lights: Z, Beam, Neon, String."""

    _effect_key = "multizone_effect"

    def __init__(
        self,
        transport: LifxTransport,
        device_info: DeviceInfo,
        target_mac: bytes,
        zone_count: int = 1,
        kelvin: int = 3500,
        *,
        caps: DeviceCapabilities | None = None,
    ) -> None:
        super().__init__(
            transport,
            device_info,
            target_mac,
            kelvin=kelvin,
            caps=caps
            or DeviceCapabilities(protocol="LIFX", multizone=True, extended_multizone=True),
        )
        self._zone_count = zone_count

    @property
    def led_count(self) -> int:
        return self._zone_count

    @property
    def geometry(self) -> DeviceGeometry:
        return StripGeometry(direction=(1, 0, 0), length=1.0)

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        hsbk = rgb_array_to_hsbk(colors, kelvin=self._kelvin)
        for start in range(0, len(hsbk), MAX_ZONES_PER_PACKET):
            chunk = hsbk[start : start + MAX_ZONES_PER_PACKET]
            values: list[HSBK] = [(int(c[0]), int(c[1]), int(c[2]), int(c[3])) for c in chunk]
            self._send(
                SET_EXTENDED_COLOR_ZONES,
                build_set_extended_color_zones(0, 1, start, len(values), values),
            )

    async def set_zone_colours(self, colours: Sequence[HSBK], duration_ms: int = 0) -> None:
        for start in range(0, len(colours), MAX_ZONES_PER_PACKET):
            chunk = list(colours[start : start + MAX_ZONES_PER_PACKET])
            await self._command(
                SET_EXTENDED_COLOR_ZONES,
                build_set_extended_color_zones(duration_ms, 1, start, len(chunk), chunk),
                STATE_EXTENDED_COLOR_ZONES,
            )

    async def start_multizone_effect(
        self, effect: MultiZoneEffectType, speed_ms: int, *, reverse: bool = False
    ) -> None:
        await self._command(
            SET_MULTIZONE_EFFECT,
            build_set_multizone_effect(effect, speed_ms, reverse=reverse),
            STATE_MULTIZONE_EFFECT,
        )

    async def multizone_effect(self) -> MultiZoneEffectState | None:
        return await self._query(
            GET_MULTIZONE_EFFECT, b"", STATE_MULTIZONE_EFFECT, parse_state_multizone_effect
        )

    async def _stop_effect(self) -> None:
        await self.start_multizone_effect(MultiZoneEffectType.OFF, 0)

    async def _start_effect(self, saved: dict[str, Any]) -> None:
        await self.start_multizone_effect(
            MultiZoneEffectType(int(saved["effect"])),
            int(saved["speed_ms"]),
            reverse=bool(saved["reverse"]),
        )

    async def _zone_colours(self) -> list[HSBK] | None:
        return await self._query(
            GET_EXTENDED_COLOR_ZONES, b"", STATE_EXTENDED_COLOR_ZONES, _colours_of_zones
        )

    async def _capture_extra(self) -> dict[str, Any]:
        extra: dict[str, Any] = {}
        zones = await self._zone_colours()
        if zones:
            extra["zones"] = [list(zone) for zone in zones]
        effect = await self.multizone_effect()
        if effect is not None and effect.effect != MultiZoneEffectType.OFF:
            extra["multizone_effect"] = {
                "effect": effect.effect,
                "speed_ms": effect.speed_ms,
                "reverse": effect.reverse,
            }
        return extra

    async def _restore_colours(self, snapshot: dict[str, Any], hsbk: HSBK) -> None:
        zones = snapshot.get("zones")
        if isinstance(zones, list) and zones:
            try:
                await self.set_zone_colours([hsbk_from_json(z) for z in zones], RESTORE_FADE_MS)
                return
            except (FirmwareRejected, NoAnswer, ValueError):
                logger.warning("LIFX '{}': couldn't restore its zones", self._device_info.name)
        await super()._restore_colours(snapshot, hsbk)
