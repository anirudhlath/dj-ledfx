"""A home for ZoneManager tests: real stores on a temporary state.db, FakeLights, and
fakes for the engine (it hosts runtimes) and the scheduler (it holds routes)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from conftest import FakeLight

from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.devices.manager import DeviceManager
from dj_ledfx.effects.ledset import NO_SPACE, PlacedLeds, Space
from dj_ledfx.events import EventBus
from dj_ledfx.home.map import HomeMap
from dj_ledfx.home.model import Home as HomeModel
from dj_ledfx.home.store import HomeStore
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.looks.model import Layer, Look
from dj_ledfx.looks.store import LookStore
from dj_ledfx.persistence.state_db import StateDB
from dj_ledfx.scheduling.route import DeviceRoute
from dj_ledfx.types import DeviceInfo
from dj_ledfx.zones.home_view import NO_HOME, HomeView, MapZones
from dj_ledfx.zones.manager import ZoneManager
from dj_ledfx.zones.model import HOME_ZONE_ID, HOME_ZONE_NAME, ZoneRecord, ZonesChanged
from dj_ledfx.zones.runtime import ZoneRuntime
from dj_ledfx.zones.store import ZoneStore

TILE = DeviceCapabilities(protocol="LIFX", matrix=True)
GLOW_LAYER = Layer(id="glow", name="Glow", type="firmware", kind="glow_firmware")
GLOW = Look(id="glow", name="Glow look", category="firmware", layers=(GLOW_LAYER,))
BREATHE_AND_GLOW = Look(
    id="breathe-glow",
    name="Breathe and glow",
    category="ambient",
    layers=(Layer(id="field", name="Breathe", type="field", kind="breathe"), GLOW_LAYER),
)
START = datetime(2026, 9, 24, 19, 0, tzinfo=UTC)


def zone_record(zone_id: str, *lights: str, name: str | None = None) -> ZoneRecord:
    """A zone of these lights, named after its id unless a name is given."""
    return ZoneRecord(id=zone_id, name=name or zone_id.capitalize(), lights=lights)


class FakeHost:
    """Stands in for the engine: it only keeps the runtimes it is given."""

    def __init__(self) -> None:
        self.runtimes: dict[str, ZoneRuntime] = {}

    def add_runtime(self, runtime: ZoneRuntime) -> None:
        self.runtimes[runtime.key] = runtime

    def remove_runtime(self, key: str) -> None:
        self.runtimes.pop(key, None)


class FakeRoutes:
    """Stands in for the scheduler: it keeps each light's route, and sends a frame down
    every streaming route whenever the app asks a light something (send_frames), as the
    real scheduler does while the zone manager awaits."""

    def __init__(self, lights: Mapping[str, FakeLight]) -> None:
        self.routes: dict[str, DeviceRoute] = {}
        self._lights = lights

    def send_frames(self) -> None:
        for device_id, route in self.routes.items():
            light = self._lights.get(device_id)
            if light is None or not light.connected or not route.streaming:
                continue
            light.receive_frame(np.zeros((light.led_count, 3), dtype=np.uint8))

    def set_route(self, device_id: str, route: DeviceRoute | None) -> None:
        if route is None:
            self.routes.pop(device_id, None)
        else:
            self.routes[device_id] = route


@dataclass
class FakeHome:
    """Stands in for the home map (zones/home_view.py): rooms and sub-zones with the lights
    in them, in order. A test moves a light by changing these, then calls
    manager.home_changed(), as the map's listener does. Room names are their ids,
    capitalised."""

    rooms: dict[str, list[str]] = field(default_factory=dict)
    sub_zones: dict[str, list[str]] = field(default_factory=dict)
    unplaced: list[str] = field(default_factory=list)  # in the whole home, in no room
    placed_at: dict[str, PlacedLeds] = field(default_factory=dict)
    space_now: Space = NO_SPACE

    def zone_records(self) -> list[ZoneRecord]:
        return [
            ZoneRecord(HOME_ZONE_ID, HOME_ZONE_NAME, "home"),
            *(ZoneRecord(room, room.capitalize(), "room") for room in self.rooms),
            *(ZoneRecord(sub, sub.capitalize(), "sub-zone") for sub in self.sub_zones),
        ]

    def members(self, zone_id: str) -> tuple[str, ...]:
        if zone_id == HOME_ZONE_ID:
            placed = [light for lights in self.rooms.values() for light in lights]
            return tuple(dict.fromkeys([*placed, *self.unplaced]))
        return tuple(self.rooms.get(zone_id) or self.sub_zones.get(zone_id) or ())

    def covers(self, device_ids: Iterable[str]) -> tuple[str, ...]:
        ids = set(device_ids)
        return tuple(room.capitalize() for room, lights in self.rooms.items() if ids & set(lights))

    def placed(self, device_id: str) -> PlacedLeds | None:
        return self.placed_at.get(device_id)

    def room_of(self, device_id: str) -> str | None:
        return next((room for room, lights in self.rooms.items() if device_id in lights), None)

    def room_index(self) -> dict[str, int]:
        return {room: index for index, room in enumerate(self.rooms)}

    def space(self) -> Space:
        return self.space_now


@dataclass
class Home:
    db: StateDB
    lights: dict[str, FakeLight]
    devices: DeviceManager
    store: ZoneStore
    looks: LookStore
    host: FakeHost
    routes: FakeRoutes
    bus: EventBus
    manager: ZoneManager
    clock: list[datetime]  # the manager's "now"; tests move it
    view: HomeView = NO_HOME  # the home map the manager asks
    home_map: HomeMap | None = None  # a real map, with build_home(plan=...)
    changes: list[ZonesChanged] = field(default_factory=list)

    def look(self, look_id: str) -> Look:
        return self.looks.get(look_id)

    async def restart(self, *, preview_only: bool = False, ghosts: bool = False) -> Home:
        """The app starting again on the same state.db and lights, then resuming.

        With ghosts, as main does it: every light is registered offline from what
        state.db knows, and resume runs before any of them connects (see come_online).
        """
        for light in self.lights.values():
            light.calls.clear()
        home = await assemble(
            self.db,
            list(self.lights.values()),
            self.clock,
            preview_only,
            ghosts=ghosts,
            view=self.view,
            with_map=self.home_map is not None,
        )
        await home.manager.resume()
        return home

    async def come_online(self, device_id: str) -> None:
        """A light connecting after a restart, as main wires it: its ghost is promoted,
        then the zone manager gets one online event."""
        self.devices.promote_device(device_id, self.lights[device_id])
        await self.manager.on_device_online(device_id)


HomeFactory = Callable[..., Awaitable[Home]]


async def build_home(
    tmp_path: Path,
    lights: Sequence[FakeLight],
    zones: Sequence[ZoneRecord],
    *,
    preview_only: bool = False,
    view: HomeView | None = None,
    frames_watched: Callable[[], bool] | None = None,
    plan: HomeModel | None = None,
) -> Home:
    db = StateDB(tmp_path / "state.db")
    await db.open()
    store = ZoneStore(db)
    for zone in zones:
        await store.save_zone(zone)
    if plan is not None:
        home_store = HomeStore(db)
        await home_store.save_home(plan)
        await home_store.mark_placements_seeded({})  # tests place their lights themselves
    return await assemble(
        db,
        lights,
        [START],
        preview_only,
        view=view,
        frames_watched=frames_watched,
        with_map=plan is not None,
    )


async def assemble(
    db: StateDB,
    lights: Sequence[FakeLight],
    clock: list[datetime],
    preview_only: bool,
    *,
    ghosts: bool = False,
    view: HomeView | None = None,
    frames_watched: Callable[[], bool] | None = None,
    with_map: bool = False,
) -> Home:
    """The app's objects around an open state.db and a set of lights."""
    bus = EventBus()
    devices = DeviceManager()
    for light in lights:
        tracker = LatencyTracker(strategy=StaticLatency(20.0))
        if not ghosts:
            devices.add_device(light, tracker)
            continue
        info = light.device_info  # a ghost knows only state.db's row, as in main
        row = DeviceInfo(
            name=info.name,
            device_type=info.backend or "",
            led_count=info.led_count,
            address="",
            stable_id=info.stable_id,
        )
        devices.add_device_from_info(row, tracker, status="offline")
    home_map = None
    if with_map:  # as main wires it (Task 22): the zones follow the map
        home_map = HomeMap(HomeStore(db), devices, seeds=lambda: (), now=lambda: clock[0])
        await home_map.load()
        view = MapZones(home_map)
    looks = LookStore(db)
    await looks.load()
    store = ZoneStore(db)
    by_id = {light.stable_id: light for light in lights}
    host, routes = FakeHost(), FakeRoutes(by_id)
    for light in lights:
        light.on_io = routes.send_frames
    manager = ZoneManager(
        store=store,
        looks=looks,
        devices=devices,
        db=db,
        host=host,
        routes=routes,
        event_bus=bus,
        clock=BeatClock(),
        preview_only=preview_only,
        now=lambda: clock[0],
        home=view or NO_HOME,
        frames_watched=frames_watched or (lambda: True),
    )
    if home_map is not None:
        home_map.on_change(manager.home_changed)
    home = Home(
        db=db,
        lights=by_id,
        devices=devices,
        store=store,
        looks=looks,
        host=host,
        routes=routes,
        bus=bus,
        manager=manager,
        clock=clock,
        view=view or NO_HOME,
        home_map=home_map,
    )
    bus.subscribe(ZonesChanged, home.changes.append)
    await manager.load()
    return home
