"""What the zone manager asks of the home map (spec §4.3, §6).

The whole home, each room and each sub-zone is a zone that holds whichever lights the map
puts inside it: a light is in the room its placement's centre lies in, and a PC part
without a placement of its own is where the PC is. Members come west to east, then north
to south, unplaced lights last, so a strip effect played in LED order runs across the
room.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Protocol

from dj_ledfx.effects.ledset import NO_SPACE, PlacedLeds, Space
from dj_ledfx.home.geometry import point_in_polygon
from dj_ledfx.home.shapes import shape_centre
from dj_ledfx.zones.model import HOME_ZONE_ID, HOME_ZONE_NAME, ZoneRecord

if TYPE_CHECKING:
    from dj_ledfx.home.map import HomeMap

_NOWHERE = (math.inf, math.inf)


class HomeView(Protocol):
    def zone_records(self) -> list[ZoneRecord]:
        """The whole home, then the rooms and the sub-zones, in map order."""
        ...

    def members(self, zone_id: str) -> tuple[str, ...]:
        """The device ids a derived zone holds; () for any other id."""
        ...

    def covers(self, device_ids: Iterable[str]) -> tuple[str, ...]:
        """The names of the rooms these devices are in, in map order."""
        ...

    def placed(self, device_id: str) -> PlacedLeds | None: ...

    def room_of(self, device_id: str) -> str | None: ...

    def room_index(self) -> Mapping[str, int]: ...

    def space(self) -> Space: ...


class _NoHome:
    """No map: no derived zones, and every light unplaced (M1's behaviour)."""

    def zone_records(self) -> list[ZoneRecord]:
        return []

    def members(self, zone_id: str) -> tuple[str, ...]:
        return ()

    def covers(self, device_ids: Iterable[str]) -> tuple[str, ...]:
        return ()

    def placed(self, device_id: str) -> PlacedLeds | None:
        return None

    def room_of(self, device_id: str) -> str | None:
        return None

    def room_index(self) -> Mapping[str, int]:
        return {}

    def space(self) -> Space:
        return NO_SPACE


NO_HOME: HomeView = _NoHome()


class MapZones:
    """The home map as zones."""

    def __init__(self, home_map: HomeMap) -> None:
        self._map = home_map

    def zone_records(self) -> list[ZoneRecord]:
        home = self._map.home
        return [
            ZoneRecord(HOME_ZONE_ID, HOME_ZONE_NAME, "home"),
            *(ZoneRecord(room.id, room.name, "room") for room in home.rooms),
            *(ZoneRecord(sub.id, sub.name, "sub-zone") for sub in home.sub_zones),
        ]

    def members(self, zone_id: str) -> tuple[str, ...]:
        home = self._map.home
        devices = [device for entry in self._map.lights().entries for device in entry.devices]
        where = self._where(devices)
        if zone_id == HOME_ZONE_ID:
            chosen = devices
        elif home.room(zone_id) is not None:
            chosen = [device for device in devices if self._map.room_of(device) == zone_id]
        elif (sub := home.sub_zone(zone_id)) is not None:
            chosen = [
                device
                for device in devices
                if device in where and point_in_polygon(where[device], sub.polygon)
            ]
        else:
            return ()
        return tuple(sorted(chosen, key=lambda device: where.get(device, _NOWHERE)))

    def covers(self, device_ids: Iterable[str]) -> tuple[str, ...]:
        rooms = {self._map.room_of(device) for device in device_ids}
        return tuple(room.name for room in self._map.home.rooms if room.id in rooms)

    def placed(self, device_id: str) -> PlacedLeds | None:
        return self._map.placed(device_id)

    def room_of(self, device_id: str) -> str | None:
        return self._map.room_of(device_id)

    def room_index(self) -> Mapping[str, int]:
        return self._map.room_index()

    def space(self) -> Space:
        return self._map.space()

    def _where(self, devices: Iterable[str]) -> dict[str, tuple[float, float]]:
        """Each placed device's centre on the plan."""
        where: dict[str, tuple[float, float]] = {}
        for device in devices:
            placement = self._map.placement_for(device)
            if placement is not None:
                x, y, _ = shape_centre(placement.shape)
                where[device] = (x, y)
        return where
