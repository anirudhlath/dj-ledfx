"""The home map service (spec §6): the map and each light's placement, the questions the
zones and the web app ask of them, the owner's edits, and change listeners.

Every edit is saved first, then the in-memory map changes, then the listeners run, outside
the lock, so each sees the new map. A listener that fails is logged; it never undoes the
edit. Placements are keyed by target id: a light's id, or a PC part's device id.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import replace
from datetime import datetime
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, TypeVar

import numpy as np
from loguru import logger

from dj_ledfx.devices.lights import LightIndex
from dj_ledfx.effects.ledset import PlacedLeds, Space
from dj_ledfx.home.geometry import point_in_polygon
from dj_ledfx.home.guess import GUESS_HEIGHT_M, first_placements, guess_placements
from dj_ledfx.home.model import (
    Anchor,
    Home,
    HomeError,
    HomeNotFoundError,
    SubZone,
    home_from_dict,
    home_to_dict,
    polygon_of,
    vec3,
)
from dj_ledfx.home.seed import SeedLight, normalise_name, seed_home, seed_lights
from dj_ledfx.home.shapes import (
    LightShape,
    Placement,
    check_led_order,
    led_positions,
    shape_centre,
)
from dj_ledfx.timing import utcnow

if TYPE_CHECKING:
    from dj_ledfx.devices.manager import DeviceManager
    from dj_ledfx.home.store import HomeStore

Listener = Callable[[], Awaitable[None]]
T = TypeVar("T")

SETTINGS = ("northOffsetDeg", "ceiling", "beams", "location")
# Zone ids a sub-zone can't take: the whole home's and M1's all-lights zone (zones/ checks
# that these match its own constants). Group ids start with "group-".
RESERVED_ZONE_IDS = frozenset({"home", "all-lights"})


def _slug(name: str) -> str:
    return normalise_name(name).replace(" ", "-") or "item"


def _unique(base: str, taken: set[str] | frozenset[str]) -> str:
    candidate, number = base, 2
    while candidate in taken:
        candidate, number = f"{base}-{number}", number + 1
    return candidate


def _checked(home: Home) -> Home:
    """The map as home_from_dict reads it: every rule of a stored map, checked."""
    return home_from_dict(home_to_dict(home))


def space_of(home: Home) -> Space:
    """What a zone's effects know of the map: anchors, rooms, ceiling and the centre."""
    anchors = {a.id: np.asarray(a.position, dtype=np.float32) for a in home.anchors}
    points = {
        a.id: np.asarray(a.points or (a.position,), dtype=np.float32).reshape(-1, 3)
        for a in home.anchors
    }
    xs = [x for x, _ in home.outline]
    ys = [y for _, y in home.outline]
    return Space(
        anchors=MappingProxyType(anchors),
        anchor_points=MappingProxyType(points),
        rooms=tuple(room.id for room in home.rooms),
        ceiling=home.ceiling,
        centre=((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0, GUESS_HEIGHT_M),
    )


class HomeMap:
    def __init__(
        self,
        store: HomeStore,
        devices: DeviceManager,
        *,
        seeds: Callable[[], Sequence[SeedLight]] = seed_lights,
        now: Callable[[], datetime] = utcnow,
    ) -> None:
        self._store = store
        self._devices = devices
        self._seeds = seeds
        self._now = now
        self._home = seed_home()  # until load()
        self._placements: dict[str, Placement] = {}
        self._space: Space | None = None
        self._listeners: list[Listener] = []
        self._lock = asyncio.Lock()

    async def load(self) -> None:
        """Read the map and the placements. On the first start that knows any lights,
        place them once: seeds, then the old scene placements, then a spread."""
        self._home = await self._store.load_home()
        self._placements = await self._store.load_placements()
        self._space = None
        lights = self.lights().entries
        if not lights or await self._store.placements_seeded():
            return
        scene = await self._store.load_scene_placements()
        first = first_placements(self._home, lights, self._seeds(), scene)
        fresh = {target: p for target, p in first.items() if target not in self._placements}
        await self._store.mark_placements_seeded(fresh)
        self._placements.update(fresh)
        logger.info("Placed {} light(s) on the home map, unconfirmed", len(fresh))

    # --- queries ---------------------------------------------------------------------

    @property
    def home(self) -> Home:
        return self._home

    @property
    def placements(self) -> Mapping[str, Placement]:
        return MappingProxyType(self._placements)

    def lights(self) -> LightIndex:
        return self._devices.lights

    def placement(self, target_id: str) -> Placement | None:
        return self._placements.get(target_id)

    def placement_for(self, target_id: str) -> Placement | None:
        """The target's own placement, else, for a PC part, the PC's."""
        own = self._placements.get(target_id)
        if own is not None:
            return own
        light_id = self.lights().light_of(target_id)
        return self._placements.get(light_id) if light_id != target_id else None

    def placed(self, device_id: str) -> PlacedLeds | None:
        """Where the device's LEDs sit, or None while it isn't placed."""
        managed = self._devices.get_by_stable_id(device_id)
        if managed is None:
            return None
        adapter = managed.adapter
        own = self._placements.get(device_id)
        if own is not None:
            return led_positions(own.shape, adapter.led_count, own.led_order, adapter.geometry)
        index = self.lights()
        entry = index.get(index.light_of(device_id))
        shared = self._placements.get(entry.id) if entry is not None else None
        if entry is None or shared is None:
            return None
        for part, start, stop in entry.part_slices():  # a PC part takes the PC's placement
            if part.id == device_id:
                whole = led_positions(shared.shape, entry.leds, shared.led_order)
                return PlacedLeds.from_positions(whole.pos[start:stop])
        return None  # a device with no LEDs

    def room_at(self, x: float, y: float) -> str | None:
        return next(
            (room.id for room in self._home.rooms if point_in_polygon((x, y), room.polygon)),
            None,
        )

    def sub_zone_at(self, x: float, y: float) -> str | None:
        return next(
            (sub.id for sub in self._home.sub_zones if point_in_polygon((x, y), sub.polygon)),
            None,
        )

    def room_of(self, target_id: str) -> str | None:
        placement = self.placement_for(target_id)
        if placement is None:
            return None
        x, y, _ = shape_centre(placement.shape)
        return self.room_at(x, y)

    def sub_zone_of(self, target_id: str) -> str | None:
        placement = self.placement_for(target_id)
        if placement is None:
            return None
        x, y, _ = shape_centre(placement.shape)
        return self.sub_zone_at(x, y)

    def rooms_with_lights(self) -> frozenset[str]:
        """The rooms any light, or PC part, is placed in now."""
        return frozenset(
            room
            for entry in self.lights().entries
            for device in entry.devices
            if (room := self.room_of(device)) is not None
        )

    def room_index(self) -> dict[str, int]:
        return {room.id: index for index, room in enumerate(self._home.rooms)}

    def space(self) -> Space:
        if self._space is None:
            self._space = space_of(self._home)
        return self._space

    # --- edits -----------------------------------------------------------------------

    def on_change(self, listener: Listener) -> None:
        self._listeners.append(listener)

    async def update(self, changes: Mapping[str, Any]) -> Home:
        """Change the map's settings (web spec §12.3 PUT /home: north, ceiling, beams,
        location), in home.json's keys."""
        unknown = sorted(set(changes) - set(SETTINGS))
        if unknown:
            raise HomeError(
                f"{', '.join(unknown)} can't be changed here; only {', '.join(SETTINGS)}"
            )
        async with self._lock:
            data = home_to_dict(self._home)
            data.update(changes)
            home = home_from_dict(data)
            await self._save(home)
        await self._changed()
        return home

    async def add_anchor(
        self, name: str, position: Sequence[float], points: Sequence[Sequence[float]] = ()
    ) -> Anchor:
        async with self._lock:
            anchor_id = _unique(_slug(name), {anchor.id for anchor in self._home.anchors})
            anchor = Anchor(
                id=anchor_id,
                name=name,
                position=vec3(position, "The anchor's position"),
                points=tuple(vec3(point, "The anchor's points") for point in points),
            )
            home = _checked(replace(self._home, anchors=(*self._home.anchors, anchor)))
            await self._save(home)
        await self._changed()
        return self._found(home.anchor(anchor_id), f"No anchor '{anchor_id}'")

    async def update_anchor(
        self,
        anchor_id: str,
        *,
        name: str | None = None,
        position: Sequence[float] | None = None,
        points: Sequence[Sequence[float]] | None = None,
        confirmed: bool | None = None,
    ) -> Anchor:
        async with self._lock:
            old = self._found(self._home.anchor(anchor_id), f"No anchor '{anchor_id}'")
            new = replace(
                old,
                name=old.name if name is None else name,
                position=old.position
                if position is None
                else vec3(position, "The anchor's position"),
                points=old.points
                if points is None
                else tuple(vec3(point, "The anchor's points") for point in points),
                confirmed=old.confirmed if confirmed is None else confirmed,
            )
            anchors = tuple(
                new if anchor.id == anchor_id else anchor for anchor in self._home.anchors
            )
            home = _checked(replace(self._home, anchors=anchors))
            await self._save(home)
        await self._changed()
        return self._found(home.anchor(anchor_id), f"No anchor '{anchor_id}'")

    async def delete_anchor(self, anchor_id: str) -> None:
        async with self._lock:
            self._found(self._home.anchor(anchor_id), f"No anchor '{anchor_id}'")
            anchors = tuple(anchor for anchor in self._home.anchors if anchor.id != anchor_id)
            await self._save(replace(self._home, anchors=anchors))
        await self._changed()

    async def add_sub_zone(
        self, name: str, room: str, polygon: Sequence[Sequence[float]]
    ) -> SubZone:
        async with self._lock:
            taken = {r.id for r in self._home.rooms} | {s.id for s in self._home.sub_zones}
            base = _slug(name)
            if base.startswith("group-"):
                base = f"sub-{base}"
            sub_id = _unique(base, taken | RESERVED_ZONE_IDS)
            sub = SubZone(sub_id, name, room, polygon_of(polygon, "The sub-zone"))
            home = _checked(replace(self._home, sub_zones=(*self._home.sub_zones, sub)))
            await self._save(home)
        await self._changed()
        return self._found(home.sub_zone(sub_id), f"No sub-zone '{sub_id}'")

    async def update_sub_zone(
        self,
        sub_zone_id: str,
        *,
        name: str | None = None,
        room: str | None = None,
        polygon: Sequence[Sequence[float]] | None = None,
    ) -> SubZone:
        async with self._lock:
            old = self._found(self._home.sub_zone(sub_zone_id), f"No sub-zone '{sub_zone_id}'")
            new = replace(
                old,
                name=old.name if name is None else name,
                room=old.room if room is None else room,
                polygon=old.polygon if polygon is None else polygon_of(polygon, "The sub-zone"),
            )
            subs = tuple(new if sub.id == sub_zone_id else sub for sub in self._home.sub_zones)
            home = _checked(replace(self._home, sub_zones=subs))
            await self._save(home)
        await self._changed()
        return self._found(home.sub_zone(sub_zone_id), f"No sub-zone '{sub_zone_id}'")

    async def delete_sub_zone(self, sub_zone_id: str) -> None:
        async with self._lock:
            self._found(self._home.sub_zone(sub_zone_id), f"No sub-zone '{sub_zone_id}'")
            subs = tuple(sub for sub in self._home.sub_zones if sub.id != sub_zone_id)
            await self._save(replace(self._home, sub_zones=subs))
        await self._changed()

    async def set_placement(
        self, target_id: str, shape: LightShape, led_order: str | None = None
    ) -> Placement:
        """Place or move a light or a PC part. Moving keeps whether it was confirmed, and
        keeps the LED order when the shape's kind stays the same and none is given."""
        self._check_target(target_id)
        async with self._lock:
            old = self._placements.get(target_id)
            if led_order is None and old is not None and old.shape.kind == shape.kind:
                led_order = old.led_order
            placement = Placement(
                shape=shape,
                led_order=check_led_order(shape.kind, led_order),
                confirmed=old.confirmed if old is not None else False,
                confirmed_at=old.confirmed_at if old is not None else None,
            )
            await self._store.save_placement(target_id, placement)
            self._placements[target_id] = placement
        await self._changed()
        return placement

    async def confirm(self, target_id: str) -> Placement:
        """Confirming is explicit (spec §6.2). It moves nothing, so no listener runs."""
        async with self._lock:
            old = self._placements.get(target_id)
            if old is None:
                raise HomeNotFoundError(f"'{target_id}' has no placement to confirm")
            placement = replace(old, confirmed=True, confirmed_at=self._now())
            await self._store.save_placement(target_id, placement)
            self._placements[target_id] = placement
        return placement

    async def remove_placement(self, target_id: str) -> None:
        """Take a light off the map (web spec §8.6's "Remove from the map")."""
        self._check_target(target_id)
        async with self._lock:
            if target_id not in self._placements:
                return
            await self._store.delete_placement(target_id)
            del self._placements[target_id]
        await self._changed()

    async def guess(self) -> dict[str, Placement]:
        """Place every light that has no placement (web spec §12.3), unconfirmed."""
        async with self._lock:
            guesses = guess_placements(
                self._home, self.lights().entries, set(self._placements), self._seeds()
            )
            for target_id, placement in guesses.items():
                await self._store.save_placement(target_id, placement)
                self._placements[target_id] = placement
        if guesses:
            await self._changed()
        return guesses

    # --- internals -------------------------------------------------------------------

    @staticmethod
    def _found(item: T | None, message: str) -> T:
        if item is None:
            raise HomeNotFoundError(message)
        return item

    def _check_target(self, target_id: str) -> None:
        index = self.lights()
        if index.get(target_id) is not None:
            return
        entry = index.get(index.light_of(target_id))
        if entry is not None and any(part.id == target_id for part in entry.parts):
            return
        raise HomeNotFoundError(f"No light '{target_id}'")

    async def _save(self, home: Home) -> None:
        await self._store.save_home(home)
        self._home = home
        self._space = None

    async def _changed(self) -> None:
        for listener in list(self._listeners):
            try:
                await listener()
            except Exception:
                logger.exception("A home map listener failed; the change stands")
