"""Zones at run time: start, take-over, Off, brightness, Restart and Stop all (spec §4.3).

The manager owns which running zone each light belongs to, and everything dj-ledfx asks
of the lights (spec §6.4): it captures a light the first time dj-ledfx takes control of
it, switches it on when a look is applied, runs firmware layers on the lights that claim
them, and puts the light back how it was when it leaves every running zone. Captures are
saved in state.db, so Off still works after a restart. A light that couldn't be captured
is saved as an empty capture: Off leaves it alone rather than guessing (spec §8).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol, TypeVar

from loguru import logger

from dj_ledfx.devices.capabilities import FirmwareRejected, LightReading
from dj_ledfx.effects.registry import get_strip_effect_classes
from dj_ledfx.looks.builtin import classic_look_id
from dj_ledfx.looks.model import (
    LookNotFoundError,
    look_from_dict,
    validate_look,
    visible_field_layer,
)
from dj_ledfx.looks.store import look_body
from dj_ledfx.zones.model import (
    Assignment,
    CrashInfo,
    PreviewOnlyChanged,
    RunningZoneInfo,
    StartResult,
    TakeOver,
    ZoneError,
    ZoneNotFoundError,
    ZoneNotRunningError,
    ZoneRecord,
    ZonesChanged,
)
from dj_ledfx.zones.runtime import LightMode, ZoneLight, ZoneRuntime, ZoneState
from dj_ledfx.zones.store import new_group_id

if TYPE_CHECKING:
    from dj_ledfx.beat.clock import BeatClock
    from dj_ledfx.devices.adapter import DeviceAdapter
    from dj_ledfx.devices.manager import DeviceManager
    from dj_ledfx.effects.field import FieldEffect
    from dj_ledfx.events import EventBus
    from dj_ledfx.looks.model import Look
    from dj_ledfx.looks.store import LookStore
    from dj_ledfx.persistence.state_db import StateDB
    from dj_ledfx.scheduling.route import DeviceRoute
    from dj_ledfx.zones.store import ZoneStore

# What a light was last given: its runtime's generation (unique across runtimes) and the
# firmware layer it runs (None: it streams).
AppliedKey = tuple[int, str | None]
T = TypeVar("T")


class RuntimeHost(Protocol):
    """Renders the running zones: the effect engine."""

    def add_runtime(self, runtime: ZoneRuntime) -> None: ...

    def remove_runtime(self, zone_id: str) -> None: ...


class RouteTable(Protocol):
    """Sends each light its slice of its zone's frames: the scheduler."""

    def set_route(self, device_id: str, route: DeviceRoute | None) -> None: ...


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _applied_key(runtime: ZoneRuntime, device_id: str) -> AppliedKey:
    """What a light is given once its zone's look is applied to it."""
    claim = runtime.claim_for(device_id)
    return runtime.generation, claim[0].id if claim is not None else None


def _brightness_of(running: _Running) -> float:
    if running.runtime is not None:
        return running.runtime.brightness
    return running.saved.brightness if running.saved is not None else 1.0


def _with_settings(look: Look, changes: Mapping[str, Any]) -> Look:
    """The look with new settings on its visible field layer."""
    field = visible_field_layer(look)
    return replace(
        look,
        layers=tuple(
            replace(layer, settings={**layer.settings, **changes}) if layer is field else layer
            for layer in look.layers
        ),
    )


@dataclass
class _Running:
    since: datetime
    lights: list[str]  # the lights the zone owns after take-overs, in zone order
    runtime: ZoneRuntime | None  # None while the saved look can't be read (spec §8)
    saved: Assignment | None = None  # the assignment as saved, while runtime is None
    broken: CrashInfo | None = None  # why runtime is None


class ZoneManager:
    def __init__(
        self,
        *,
        store: ZoneStore,
        looks: LookStore,
        devices: DeviceManager,
        db: StateDB,
        host: RuntimeHost,
        routes: RouteTable,
        event_bus: EventBus,
        clock: BeatClock,
        fps: int = 60,
        max_lookahead_s: float = 1.0,
        preview_only: bool = False,
        now: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._store = store
        self._looks = looks
        self._devices = devices
        self._db = db
        self._host = host
        self._routes = routes
        self._event_bus = event_bus
        self._clock = clock
        self._fps = fps
        self._max_lookahead_s = max_lookahead_s
        self._preview_only = preview_only
        self._now = now
        self._zones: dict[str, ZoneRecord] = {}
        self._running: dict[str, _Running] = {}
        self._captured: dict[str, bytes] = {}  # b"": control taken, nothing captured
        self._applied: dict[str, AppliedKey] = {}
        self._power: dict[str, bool | None] = {}
        self._deferred_power_on: set[str] = set()
        self._seen_states: dict[str, ZoneState] = {}
        self._lock = asyncio.Lock()

    async def load(self) -> None:
        self._zones = {zone.id: zone for zone in await self._store.load_zones()}
        self._captured = await self._db.load_all_device_states()

    # --- queries ----------------------------------------------------------------------

    @property
    def preview_only(self) -> bool:
        return self._preview_only

    def zones(self) -> list[ZoneRecord]:
        return [replace(zone, lights=self._lights_of(zone)) for zone in self._zones.values()]

    def get_zone(self, zone_id: str) -> ZoneRecord:
        zone = self._zones.get(zone_id)
        if zone is None:
            raise ZoneNotFoundError(zone_id)
        return replace(zone, lights=self._lights_of(zone))

    def running(self) -> list[RunningZoneInfo]:
        infos = [self._info(zone_id, running) for zone_id, running in self._running.items()]
        return sorted(infos, key=lambda info: info.since)

    def running_info(self, zone_id: str) -> RunningZoneInfo | None:
        running = self._running.get(zone_id)
        return None if running is None else self._info(zone_id, running)

    def owner_of(self, device_id: str) -> str | None:
        for zone_id, running in self._running.items():
            if device_id in running.lights:
                return zone_id
        return None

    def light_mode(self, device_id: str) -> LightMode | None:
        """How a light shows its zone's look; None when no running zone owns it."""
        if self.owner_of(device_id) is None:
            return None
        runtime = self._runtime_of(device_id)
        return "streaming" if runtime is None else runtime.mode_of(device_id)

    def effect_name(self, device_id: str) -> str | None:
        """The firmware effect a light runs, or streams a copy of."""
        runtime = self._runtime_of(device_id)
        return None if runtime is None else runtime.effect_name(device_id)

    def power_of(self, device_id: str) -> bool | None:
        return self._power.get(device_id)

    # --- commands ---------------------------------------------------------------------

    async def start(self, zone_id: str, look: Look) -> StartResult:
        """Put a look on a zone. It takes its lights over from running zones (spec §4.3)."""
        validate_look(look)
        async with self._lock:
            result = await self._start(zone_id, look)
        self._event_bus.emit(ZonesChanged())
        return result

    async def off(self, zone_id: str) -> None:
        """Stop the zone's look and put its lights back how they were. Idempotent."""
        async with self._lock:
            self.get_zone(zone_id)
            released = await self._stop(zone_id)
            if not released:
                return
            await self._sync(released)
        self._event_bus.emit(ZonesChanged())

    async def stop_all(self) -> None:
        async with self._lock:
            if not self._running:
                return
            released = await self._stop(*self._running)
            await self._sync(released)
        self._event_bus.emit(ZonesChanged())

    async def set_brightness(self, zone_id: str, value: float) -> RunningZoneInfo:
        """Scale the zone's streamed frames and its firmware effects (spec §4.3)."""
        if not 0.0 <= value <= 1.0:
            raise ZoneError("Brightness must be between 0 and 1")
        async with self._lock:
            running = self._require_running(zone_id)
            if running.runtime is not None:
                running.runtime.set_brightness(value)
            elif running.saved is not None:
                running.saved = replace(running.saved, brightness=value)
            await self._persist(zone_id)
            await self._sync(running.lights)
            info = self._info(zone_id, running)
        self._event_bus.emit(ZonesChanged())
        return info

    async def restart(self, zone_id: str) -> RunningZoneInfo:
        """Re-create the zone's look (spec §8); rejected firmware effects get another try."""
        async with self._lock:
            running = self._require_running(zone_id)
            if running.runtime is not None:
                running.runtime.restart()
            elif self._rebuild_broken(zone_id, running):
                await self._persist(zone_id)
            await self._sync(running.lights)
            info = self._info(zone_id, running)
        self._event_bus.emit(ZonesChanged())
        return info

    def watch_states(self) -> None:
        """Emit ZonesChanged when a running zone changed state by itself (crashed, slow).

        A zone not seen yet counts as running: every zone starts that way, or its start
        already announced it.
        """
        states = {
            zone_id: self._info(zone_id, running).state
            for zone_id, running in self._running.items()
        }
        changed = any(self._seen_states.get(z, "running") != state for z, state in states.items())
        self._seen_states = states
        if changed:
            self._event_bus.emit(ZonesChanged())

    async def resume(self) -> None:
        """Bring back the zones that were running when the app stopped (spec §4.3, §6.4).

        Assignments replay oldest first, so take-overs come out as they were. Lights are
        captured when first reached and never switched on. A captured light that no zone
        owns any more is restored when it's reachable.
        """
        async with self._lock:
            for saved in await self._store.load_assignments():
                zone = self._zones.get(saved.zone_id)
                members = self._lights_of(zone) if zone is not None else ()
                lights = [
                    light
                    for light in saved.lights or members
                    if light in members and self._adapter(light) is not None
                ]
                if not lights:
                    logger.info(
                        "Zone {} has none of its lights left; not resuming it", saved.zone_id
                    )
                    await self._store.delete_assignments([saved.zone_id])
                    continue
                await self._take_over(saved.zone_id, lights)
                running = self._resumed(saved, lights)
                self._running[saved.zone_id] = running
                if running.runtime is not None:
                    self._host.add_runtime(running.runtime)
                await self._persist(saved.zone_id)
            await self._sync(self._known_lights())
        self._event_bus.emit(ZonesChanged())

    async def set_preview_only(self, on: bool) -> None:
        """Preview-only: looks run and stream to the web preview; the lights are left alone.

        Turning it on stops the frames at once. Turning it off sends the current state to
        the lights (spec §6.4): lights of zones started meanwhile are captured and switched
        on, lights of zones turned off are restored, once.
        """
        async with self._lock:
            if on == self._preview_only:
                return
            self._preview_only = on
            deferred: set[str] = set()
            if not on:
                deferred, self._deferred_power_on = self._deferred_power_on, set()
            await self._sync(self._known_lights(), power_on=deferred)
        self._event_bus.emit(PreviewOnlyChanged(on))

    async def on_power_reading(self, device_id: str, power: bool | None) -> None:
        """The light monitor read a light's power (every 5 s for zone lights).

        A light switched off elsewhere drops out of its zone's stream and rejoins when it's
        switched back on (spec §6.4). This never switches a light on.
        """
        if power is None:
            return
        async with self._lock:
            before = self._power.get(device_id)
            self._power[device_id] = power
            if power != before and self.owner_of(device_id) is not None:
                await self._sync([device_id])

    async def verify_firmware(self, device_id: str) -> None:
        """At each poll of a zone light that's on: apply its look again if the light didn't
        answer last time, or send its firmware effect again if something stopped it."""
        async with self._lock:
            runtime = self._runtime_of(device_id)
            adapter = self._adapter(device_id)
            if (
                runtime is None
                or adapter is None
                or self._held(runtime, adapter)
                or self._power.get(device_id) is False
            ):
                return
            if self._applied.get(device_id) != _applied_key(runtime, device_id):
                await self._sync([device_id])
                return
            claim = runtime.claim_for(device_id)
            if claim is None:
                return
            effect = claim[1]
            try:
                running = await effect.is_running(adapter)
            except Exception as exc:
                logger.debug("Couldn't ask {} about {}: {}", device_id, effect.display_name, exc)
                return
            if running is False:  # None: the light can't say, so trust it
                logger.info(
                    "{} stopped {}; sending it again",
                    adapter.device_info.name,
                    effect.display_name,
                )
                del self._applied[device_id]
                await self._sync([device_id])

    async def on_device_offline(self, device_id: str) -> None:
        """A light dropped out. It keeps its place in its zone until it's back, but gets
        no frames until it's ready for them again."""
        async with self._lock:
            self._applied.pop(device_id, None)
            self._power.pop(device_id, None)
            await self._sync([device_id])

    async def on_device_online(self, device_id: str) -> None:
        """A known light came back, or was found at start-up. It isn't switched on.

        If it came back with another LED count or other capabilities, its zone rebuilds
        its LED set and every light in the zone gets its slice of the new ring. A captured
        light that no zone owns any more is restored now.
        """
        async with self._lock:
            self._applied.pop(device_id, None)
            self._power.pop(device_id, None)
            zone_id = self.owner_of(device_id)
            runtime = self._runtime_of(device_id)
            if zone_id is not None and runtime is not None:
                lights = self._zone_lights(self._running[zone_id].lights)
                if list(runtime.lights) != lights:
                    runtime.set_lights(lights)
                    await self._sync(self._running[zone_id].lights)
                    return
            await self._sync([device_id])

    async def on_device_discovered(self, device_id: str) -> None:
        """A light seen for the first time joins the newest running all-lights zone."""
        async with self._lock:
            zone_id = self._newest_all_lights_zone()
            if zone_id is None or self.owner_of(device_id) is not None:
                return
            running = self._running[zone_id]
            self._set_lights(running, [*running.lights, device_id])
            await self._persist(zone_id)
            await self._sync(running.lights)
        self._event_bus.emit(ZonesChanged())

    # --- groups (web spec §11.3) --------------------------------------------------------

    async def create_group(self, name: str, lights: Sequence[str]) -> ZoneRecord:
        async with self._lock:
            zone = ZoneRecord(
                id=new_group_id(), name=self._group_name(name), lights=self._group_lights(lights)
            )
            await self._store.save_zone(zone)
            self._zones[zone.id] = zone
        self._event_bus.emit(ZonesChanged())
        return zone

    async def update_group(
        self, zone_id: str, *, name: str | None = None, lights: Sequence[str] | None = None
    ) -> ZoneRecord:
        """Rename a group or change its lights. A running group applies the change at once."""
        async with self._lock:
            zone = self._group(zone_id)
            if name is not None:
                zone = replace(zone, name=self._group_name(name))
            if lights is not None:
                zone = replace(zone, lights=self._group_lights(lights), all_lights=False)
            await self._store.save_zone(zone)
            self._zones[zone_id] = zone
            if lights is not None and zone_id in self._running:
                await self._regroup(zone_id, list(zone.lights))
        self._event_bus.emit(ZonesChanged())
        return self.get_zone(zone_id)

    async def delete_group(self, zone_id: str) -> None:
        """Delete a group. A running group is turned off first."""
        async with self._lock:
            self._group(zone_id)
            released = await self._stop(zone_id)
            await self._store.delete_zone(zone_id)
            del self._zones[zone_id]
            await self._sync(released)
        self._event_bus.emit(ZonesChanged())

    def _group(self, zone_id: str) -> ZoneRecord:
        zone = self._zones.get(zone_id)
        if zone is None:
            raise ZoneNotFoundError(zone_id)
        if zone.kind != "group":
            raise ZoneError(f"{zone.name} isn't a group; rooms come from the home map")
        return zone

    @staticmethod
    def _group_name(name: str) -> str:
        if not name.strip():
            raise ZoneError("A group needs a name")
        return name.strip()

    def _group_lights(self, lights: Sequence[str]) -> tuple[str, ...]:
        unique = tuple(dict.fromkeys(lights))
        if not unique:
            raise ZoneError("A group needs at least one light")
        for light in unique:
            if self._adapter(light) is None:
                raise ZoneError(f"Unknown light '{light}'")
        return unique

    async def _regroup(self, zone_id: str, members: list[str]) -> None:
        """A running group's lights changed: take over, apply and release as a start would."""
        running = self._running[zone_id]
        added = [light for light in members if light not in running.lights]
        removed = [light for light in running.lights if light not in members]
        _, touched = await self._take_over(zone_id, added)
        self._set_lights(running, members)
        await self._persist(zone_id)
        await self._sync([*members, *touched, *removed], power_on=added)

    # --- the old UI's effect deck, until F11 ---------------------------------------------

    def classic_layer(self, zone_id: str) -> tuple[str, dict[str, Any]] | None:
        """The classic effect a running zone plays, and its current settings."""
        classic = self._classic(zone_id)
        if classic is None:
            return None
        _, kind, effect = classic
        return kind, effect.get_params()

    async def set_classic_effect(
        self, zone_id: str, effect: str | None, params: Mapping[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        """Tune the classic effect a zone plays in place, or start another one's look."""
        async with self._lock:
            zone = self.get_zone(zone_id)
            classic = self._classic(zone_id)
            kind = effect or (classic[1] if classic is not None else None)
            if kind is None:
                raise ZoneNotRunningError(f"{zone.name} isn't playing a classic effect")
            if classic is not None and classic[1] == kind:
                runtime = classic[0]
                look = _with_settings(runtime.look, params)
                validate_look(look)
                runtime.update_look(look)
                await self._persist(zone_id)
                await self._sync(self._running[zone_id].lights)
            else:
                await self._start(
                    zone_id, _with_settings(self._looks.get(classic_look_id(kind)), params)
                )
            result = self.classic_layer(zone_id)
        self._event_bus.emit(ZonesChanged())
        if result is None:  # the classic look crashed as it started
            raise ZoneNotRunningError(f"{zone.name} isn't playing a classic effect")
        return result

    def _classic(self, zone_id: str) -> tuple[ZoneRuntime, str, FieldEffect] | None:
        """A running zone's runtime, its classic effect's kind, and the effect."""
        running = self._running.get(zone_id)
        runtime = running.runtime if running is not None else None
        effect = runtime.field_effect if runtime is not None else None
        if runtime is None or effect is None:
            return None
        layer = visible_field_layer(runtime.look)
        if layer is None or layer.kind not in get_strip_effect_classes():
            return None
        return runtime, layer.kind, effect

    # --- running zones ----------------------------------------------------------------

    def _require_running(self, zone_id: str) -> _Running:
        zone = self.get_zone(zone_id)
        running = self._running.get(zone_id)
        if running is None:
            raise ZoneNotRunningError(f"{zone.name} isn't running")
        return running

    async def _start(self, zone_id: str, look: Look) -> StartResult:
        validate_look(look)
        zone = self.get_zone(zone_id)
        lights = [light for light in zone.lights if self._adapter(light) is not None]
        if not lights:
            raise ZoneError(f"{zone.name} has no lights")
        take_overs, touched = await self._take_over(zone_id, lights)
        previous = self._running.pop(zone_id, None)
        if previous is not None:
            self._host.remove_runtime(zone_id)
        brightness = _brightness_of(previous) if previous is not None else 1.0
        runtime = self._new_runtime(zone_id, look, lights, brightness)
        running = _Running(since=self._now(), lights=lights, runtime=runtime)
        self._running[zone_id] = running
        self._host.add_runtime(runtime)
        await self._persist(zone_id)
        released = [x for x in previous.lights if x not in lights] if previous else []
        await self._sync([*lights, *touched, *released], power_on=lights)
        return StartResult(self._info(zone_id, running), tuple(take_overs))

    def _new_runtime(
        self, zone_id: str, look: Look, lights: Iterable[str], brightness: float
    ) -> ZoneRuntime:
        return ZoneRuntime(
            zone_id,
            look,
            self._zone_lights(lights),
            clock=self._clock,
            latency_s=self._latency_s,
            fps=self._fps,
            max_lookahead_s=self._max_lookahead_s,
            brightness=brightness,
            now=self._now,
        )

    def _rebuild_broken(self, zone_id: str, running: _Running) -> bool:
        """A zone whose saved look can't be read tries the look saved under its id."""
        saved = running.saved
        if saved is None:
            return False
        try:
            look = self._looks.get(saved.look_id)
        except LookNotFoundError:
            return False
        running.runtime = self._new_runtime(zone_id, look, running.lights, saved.brightness)
        running.saved = running.broken = None
        self._host.add_runtime(running.runtime)
        return True

    def _resumed(self, saved: Assignment, lights: list[str]) -> _Running:
        """A running zone rebuilt from its saved assignment (spec §8 for bad looks)."""
        try:
            look = replace(look_from_dict(json.loads(saved.look_json)), id=saved.look_id)
        except Exception as exc:  # a bad saved look never stops the app
            logger.error("Zone {}: the saved look can't be read: {}", saved.zone_id, exc)
            broken = CrashInfo(
                layer="", message=f"The saved look can't be read: {exc}", at=self._now()
            )
            return _Running(saved.started_at, lights, None, saved=saved, broken=broken)
        runtime = self._new_runtime(saved.zone_id, look, lights, saved.brightness)
        return _Running(saved.started_at, lights, runtime)

    def _look_name(self, running: _Running) -> str:
        if running.runtime is not None:
            return running.runtime.look.name
        look_id = running.saved.look_id if running.saved is not None else ""
        try:
            return self._looks.get(look_id).name
        except LookNotFoundError:
            return look_id

    def _newest_all_lights_zone(self) -> str | None:
        running = [
            (state.since, zone_id)
            for zone_id, state in self._running.items()
            if self._zones[zone_id].all_lights
        ]
        return max(running)[1] if running else None

    async def _take_over(
        self, zone_id: str, wanted: Iterable[str]
    ) -> tuple[list[TakeOver], list[str]]:
        """Take lights from other running zones: the newest assignment wins (spec §4.3).

        Returns the take-overs and the lights left in zones that lost some: their zone
        rebuilt its LED set, so they need new routes.
        """
        wanted_set = set(wanted)
        take_overs: list[TakeOver] = []
        touched: list[str] = []
        for other_id, other in list(self._running.items()):
            lost = [x for x in other.lights if x in wanted_set] if other_id != zone_id else []
            if not lost:
                continue
            kept = [x for x in other.lights if x not in wanted_set]
            zone_name = self._zones[other_id].name
            look_name = self._look_name(other)
            take_overs.append(TakeOver(other_id, zone_name, look_name, tuple(lost), not kept))
            if not kept:
                await self._stop(other_id)
                continue
            self._set_lights(other, kept)
            await self._persist(other_id)
            touched += kept
        return take_overs, touched

    async def _stop(self, *zone_ids: str) -> list[str]:
        """Forget running zones. Returns their lights, which the caller syncs (releases)."""
        stopped = [zone_id for zone_id in zone_ids if zone_id in self._running]
        lights: list[str] = []
        for zone_id in stopped:
            lights += self._running.pop(zone_id).lights
            self._host.remove_runtime(zone_id)
        if stopped:
            await self._store.delete_assignments(stopped)
        return lights

    def _set_lights(self, running: _Running, lights: list[str]) -> None:
        running.lights = lights
        if running.runtime is not None:
            running.runtime.set_lights(self._zone_lights(lights))

    def _runtime_of(self, device_id: str) -> ZoneRuntime | None:
        """The runtime of the zone that owns a light; None if none does, or it's broken."""
        zone_id = self.owner_of(device_id)
        return None if zone_id is None else self._running[zone_id].runtime

    async def _persist(self, zone_id: str) -> None:
        running = self._running[zone_id]
        lights, since = tuple(running.lights), running.since
        if running.saved is not None:  # kept as saved, so a later version may read it
            assignment = replace(running.saved, lights=lights, started_at=since)
        else:
            assert running.runtime is not None
            look = running.runtime.look
            assignment = Assignment(
                zone_id=zone_id,
                look_id=look.id,
                look_json=look_body(look),
                brightness=running.runtime.brightness,
                lights=lights,
                started_at=since,
            )
        await self._store.save_assignment(assignment)

    def _info(self, zone_id: str, running: _Running) -> RunningZoneInfo:
        runtime = running.runtime
        if runtime is None:
            return RunningZoneInfo(
                zone_id=zone_id,
                look_id=running.saved.look_id if running.saved is not None else "",
                look_name=self._look_name(running),
                since=running.since,
                brightness=_brightness_of(running),
                lights=tuple(running.lights),
                state="crashed",
                error=running.broken,
            )
        return RunningZoneInfo(
            zone_id=zone_id,
            look_id=runtime.look.id,
            look_name=runtime.look.name,
            since=running.since,
            brightness=runtime.brightness,
            lights=tuple(running.lights),
            state=runtime.state,
            fps_actual=runtime.fps_actual,
            fps_target=runtime.fps_target,
            error=runtime.crash,
            waiting_for=runtime.waiting_for,
            slow_since=runtime.slow_since,
        )

    # --- lights -----------------------------------------------------------------------

    def _adapter(self, device_id: str) -> DeviceAdapter | None:
        managed = self._devices.get_by_stable_id(device_id)
        return None if managed is None else managed.adapter

    def _zone_light(self, device_id: str) -> ZoneLight | None:
        adapter = self._adapter(device_id)
        if adapter is None:
            return None
        return ZoneLight(device_id, adapter.led_count, adapter.capabilities, adapter.geometry)

    def _zone_lights(self, device_ids: Iterable[str]) -> list[ZoneLight]:
        return [light for d in device_ids if (light := self._zone_light(d)) is not None]

    def _latency_s(self, device_id: str) -> float:
        managed = self._devices.get_by_stable_id(device_id)
        return 0.0 if managed is None else managed.tracker.effective_latency_s

    def _lights_of(self, zone: ZoneRecord) -> tuple[str, ...]:
        if not zone.all_lights:
            return zone.lights
        infos = (managed.adapter.device_info for managed in self._devices.devices)
        return tuple(info.stable_id for info in infos if info.stable_id)

    def _known_lights(self) -> list[str]:
        """Every light the app knows, then captured lights no device stands for yet."""
        ids = (managed.adapter.device_info.stable_id for managed in self._devices.devices)
        return list(dict.fromkeys([*(x for x in ids if x), *self._captured]))

    async def _sync(self, device_ids: Iterable[str], power_on: Iterable[str] = ()) -> None:
        """Bring each light in line with the zone that owns it, or release it.

        The lights about to get a look are read and, the first time, captured, all at once;
        the new captures are saved in one transaction before any light is changed (spec
        §4.3). Then every light is applied or released at once, and the released lights'
        captures are forgotten together.
        """
        wanted = set(power_on)
        if self._preview_only:
            self._deferred_power_on |= wanted  # applied when preview-only is turned off
        ids = list(dict.fromkeys(device_ids))
        captured = await self._each(ids, lambda d: self._look_at(d, d in wanted))
        new = {d: state for d, state in zip(ids, captured, strict=True) if state is not None}
        if new:
            await self._db.save_device_states(new)
        released = await self._each(ids, lambda d: self._sync_device(d, d in wanted))
        gone = [d for d, done in zip(ids, released, strict=True) if done]
        if gone:
            await self._db.delete_device_states(gone)

    @staticmethod
    async def _each(ids: list[str], step: Callable[[str], Awaitable[T]]) -> list[T | None]:
        """Run step for every light at once. A light that fails is logged and gives None."""
        results = await asyncio.gather(*(step(d) for d in ids), return_exceptions=True)
        out: list[T | None] = []
        for device_id, result in zip(ids, results, strict=True):
            if isinstance(result, Exception):
                logger.opt(exception=result).warning("Couldn't update light {}", device_id)
                out.append(None)
            elif isinstance(result, BaseException):
                raise result
            else:
                out.append(result)
        return out

    def _held(self, runtime: ZoneRuntime, adapter: DeviceAdapter) -> bool:
        """A zone light that's left as it is for now."""
        return (
            self._preview_only  # frames reach the web preview only
            or runtime.crash is not None  # the light holds the last frame
            or not adapter.is_connected  # offline: it rejoins when it's back
        )

    async def _look_at(self, device_id: str, power_on: bool) -> bytes | None:
        """Read a light about to get its zone's look, and capture it the first time.
        Returns the new capture, for _sync to save."""
        runtime = self._runtime_of(device_id)
        adapter = self._adapter(device_id)
        if runtime is None or adapter is None or self._held(runtime, adapter):
            return None
        if power_on or device_id not in self._power:  # a look being applied reads it afresh
            self._power[device_id] = (await self._read(adapter)).power
        if device_id in self._captured:
            return None
        state = await self._capture(adapter)
        self._captured[device_id] = state
        return state

    async def _sync_device(self, device_id: str, power_on: bool) -> bool:
        """Apply the owning zone's look to a light, or release it. True: it was released."""
        zone_id = self.owner_of(device_id)
        adapter = self._adapter(device_id)
        if zone_id is None:
            self._routes.set_route(device_id, None)
            self._applied.pop(device_id, None)
            self._power.pop(device_id, None)  # read afresh when a zone takes it again
            if adapter is None or self._preview_only:
                return False
            return await self._release(device_id, adapter)
        runtime = self._running[zone_id].runtime
        if runtime is None:  # the saved look can't be read: leave the light alone
            self._routes.set_route(device_id, None)
            return False
        if (
            adapter is None
            or self._held(runtime, adapter)
            or device_id not in self._captured  # it came back after _look_at: the next sync
        ):
            self._publish(device_id, runtime)
            return False
        if power_on and self._power.get(device_id) is not True:  # off, or it can't say
            await self._switch_on(device_id, adapter)
        if self._power.get(device_id) is False:  # switched off elsewhere: out until it's on
            self._routes.set_route(device_id, None)
            self._applied.pop(device_id, None)
            return False
        await self._apply(device_id, adapter, runtime)
        self._publish(device_id, runtime)
        return False

    def _publish(self, device_id: str, runtime: ZoneRuntime) -> None:
        """Route a light to its zone's frames. They're sent only once _apply has readied the
        light for this runtime, and never while preview-only is on; the web preview gets
        every routed slice either way."""
        route = runtime.route_for(device_id)
        applied = self._applied.get(device_id)
        ready = applied is not None and applied[0] == runtime.generation
        if route is not None and route.streaming and (self._preview_only or not ready):
            route = replace(route, streaming=False)
        self._routes.set_route(device_id, route)

    async def _apply(self, device_id: str, adapter: DeviceAdapter, runtime: ZoneRuntime) -> None:
        """Start the light's firmware layer, or get it ready to stream, once per change."""
        key = _applied_key(runtime, device_id)
        if self._applied.get(device_id) == key:
            return
        claim = runtime.claim_for(device_id)
        if claim is not None:
            layer, effect = claim
            self._routes.set_route(device_id, runtime.route_for(device_id))  # stop frames first
            try:
                async with adapter.send_lock:
                    await effect.start(adapter, effect.start_params(runtime.brightness))
            except FirmwareRejected as exc:  # it can't run it: stream a copy (spec §8)
                logger.warning(
                    "{} refused {} ({}); streaming a copy instead",
                    adapter.device_info.name,
                    effect.display_name,
                    exc,
                )
                runtime.mark_emulated(device_id)
                claim = None
                key = (runtime.generation, None)
            except Exception as exc:  # no answer: left unapplied, the next poll tries again
                logger.warning(
                    "{} didn't start {} ({}); trying again at the next poll",
                    adapter.device_info.name,
                    effect.display_name,
                    exc,
                )
                return
        if claim is None:
            try:
                await adapter.prepare_stream()
            except Exception as exc:
                logger.warning("Couldn't prepare {}: {}", adapter.device_info.name, exc)
        self._applied[device_id] = key

    async def _read(self, adapter: DeviceAdapter) -> LightReading:
        try:
            return await adapter.read_light()
        except Exception as exc:
            logger.warning("Couldn't read {}: {}", adapter.device_info.name, exc)
            return LightReading(power=None, colour=None)

    async def _capture(self, adapter: DeviceAdapter) -> bytes:
        """Capture a light before dj-ledfx first changes it (spec §4.3). b"": control is
        taken but nothing was captured, so Off leaves the light alone (spec §8)."""
        try:
            state = await adapter.capture_state()
        except Exception as exc:
            logger.warning("Couldn't capture {}: {}", adapter.device_info.name, exc)
            state = None
        if state is None:
            logger.info("{} can't be captured; Off will leave it alone", adapter.device_info.name)
        return state or b""

    async def _switch_on(self, device_id: str, adapter: DeviceAdapter) -> None:
        """Only ever called for a look being applied (spec §6.4)."""
        try:
            await adapter.set_power(True)
        except Exception as exc:
            logger.warning("Couldn't switch on {}: {}", adapter.device_info.name, exc)
            return
        self._power[device_id] = True

    async def _release(self, device_id: str, adapter: DeviceAdapter) -> bool:
        """Put a light back how it was before dj-ledfx took control, once (spec §4.3).
        True: done, so _sync forgets its capture."""
        state = self._captured.get(device_id)
        if state is None or not adapter.is_connected:
            return False  # nothing to release, or offline: released when it's back
        if state:
            # Read afresh: the last poll may be 5 s old. A light that reads off gets its
            # colour and effect back and stays off: Off never switches a light on (§6.4).
            power = (await self._read(adapter)).power
            try:
                async with adapter.send_lock:  # the route is gone; no frame lands after this
                    await adapter.restore_state(state, power=power is not False)
            except Exception as exc:
                logger.warning("Couldn't restore {}: {}", adapter.device_info.name, exc)
                return False
        del self._captured[device_id]
        return True
