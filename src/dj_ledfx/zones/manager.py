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
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol

from loguru import logger

from dj_ledfx.devices.capabilities import LightReading
from dj_ledfx.looks.model import LookNotFoundError, validate_look
from dj_ledfx.looks.store import look_body
from dj_ledfx.zones.model import (
    Assignment,
    CrashInfo,
    RunningZoneInfo,
    StartResult,
    TakeOver,
    ZoneError,
    ZoneNotFoundError,
    ZoneNotRunningError,
    ZoneRecord,
    ZonesChanged,
)
from dj_ledfx.zones.runtime import LightMode, ZoneLight, ZoneRuntime

if TYPE_CHECKING:
    from dj_ledfx.beat.clock import BeatClock
    from dj_ledfx.devices.adapter import DeviceAdapter
    from dj_ledfx.devices.manager import DeviceManager
    from dj_ledfx.events import EventBus
    from dj_ledfx.looks.model import Look
    from dj_ledfx.looks.store import LookStore
    from dj_ledfx.persistence.state_db import StateDB
    from dj_ledfx.scheduling.route import DeviceRoute
    from dj_ledfx.zones.store import ZoneStore

# What a light was last given: the runtime it belongs to, that runtime's generation, and
# the firmware layer it runs (None: it streams).
AppliedKey = tuple[int, int, str | None]


class RuntimeHost(Protocol):
    """Renders the running zones: the effect engine."""

    def add_runtime(self, runtime: ZoneRuntime) -> None: ...

    def remove_runtime(self, zone_id: str) -> None: ...


class RouteTable(Protocol):
    """Sends each light its slice of its zone's frames: the scheduler."""

    def set_route(self, device_id: str, route: DeviceRoute | None) -> None: ...

    def set_preview_only(self, on: bool) -> None: ...


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class _Running:
    look_id: str
    look_name: str
    look_json: str  # the look as it was started, as saved in state.db
    brightness: float
    since: datetime
    lights: list[str]  # the lights the zone owns after take-overs, in zone order
    runtime: ZoneRuntime | None  # None when the saved look can't be read (Task 17)
    epoch: int  # tells runtimes apart, so a new look always reaches the lights
    broken: CrashInfo | None = None


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
        self._epochs = 0
        self._lock = asyncio.Lock()
        routes.set_preview_only(preview_only)

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
        zone_id = self.owner_of(device_id)
        if zone_id is None:
            return None
        runtime = self._running[zone_id].runtime
        return "streaming" if runtime is None else runtime.mode_of(device_id)

    def effect_name(self, device_id: str) -> str | None:
        """The firmware effect a light runs, or streams a copy of."""
        zone_id = self.owner_of(device_id)
        runtime = self._running[zone_id].runtime if zone_id is not None else None
        return None if runtime is None else runtime.effect_name(device_id)

    def power_of(self, device_id: str) -> bool | None:
        return self._power.get(device_id)

    # --- commands ---------------------------------------------------------------------

    async def start(self, zone_id: str, look: Look) -> StartResult:
        """Put a look on a zone. It takes its lights over from running zones (spec §4.3)."""
        validate_look(look)
        async with self._lock:
            zone = self.get_zone(zone_id)
            lights = [light for light in zone.lights if self._adapter(light) is not None]
            if not lights:
                raise ZoneError(f"{zone.name} has no lights")
            take_overs, touched = await self._take_over(zone_id, lights)
            previous = self._running.pop(zone_id, None)
            if previous is not None:
                self._host.remove_runtime(zone_id)
            brightness = previous.brightness if previous is not None else 1.0
            runtime = self._new_runtime(zone_id, look, lights, brightness)
            running = _Running(
                look_id=look.id,
                look_name=look.name,
                look_json=look_body(look),
                brightness=brightness,
                since=self._now(),
                lights=lights,
                runtime=runtime,
                epoch=self._next_epoch(),
            )
            self._running[zone_id] = running
            self._host.add_runtime(runtime)
            await self._persist(zone_id)
            released = [x for x in previous.lights if x not in lights] if previous else []
            await self._sync([*lights, *touched, *released], power_on=lights)
            result = StartResult(self._info(zone_id, running), tuple(take_overs))
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
            released: list[str] = []
            for zone_id in list(self._running):
                released += await self._stop(zone_id)
            await self._sync(released)
        self._event_bus.emit(ZonesChanged())

    async def set_brightness(self, zone_id: str, value: float) -> RunningZoneInfo:
        """Scale the zone's streamed frames and its firmware effects (spec §4.3)."""
        if not 0.0 <= value <= 1.0:
            raise ZoneError("Brightness must be between 0 and 1")
        async with self._lock:
            running = self._require_running(zone_id)
            running.brightness = value
            if running.runtime is not None:
                running.runtime.set_brightness(value)
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

    # --- running zones ----------------------------------------------------------------

    def _require_running(self, zone_id: str) -> _Running:
        zone = self.get_zone(zone_id)
        running = self._running.get(zone_id)
        if running is None:
            raise ZoneNotRunningError(f"{zone.name} isn't running")
        return running

    def _next_epoch(self) -> int:
        self._epochs += 1
        return self._epochs

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
        try:
            look = self._looks.get(running.look_id)
        except LookNotFoundError:
            return False
        running.runtime = self._new_runtime(zone_id, look, running.lights, running.brightness)
        running.epoch = self._next_epoch()
        running.broken = None
        running.look_name = look.name
        running.look_json = look_body(look)
        self._host.add_runtime(running.runtime)
        return True

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
            other.lights = [x for x in other.lights if x not in wanted_set]
            stopped = not other.lights
            zone_name = self._zones[other_id].name
            take_overs.append(TakeOver(other_id, zone_name, other.look_name, tuple(lost), stopped))
            if stopped:
                await self._stop(other_id)
                continue
            if other.runtime is not None:
                other.runtime.set_lights(self._zone_lights(other.lights))
            await self._persist(other_id)
            touched += other.lights
        return take_overs, touched

    async def _stop(self, zone_id: str) -> list[str]:
        """Forget a running zone. Returns its lights, which the caller syncs (releases)."""
        running = self._running.pop(zone_id, None)
        if running is None:
            return []
        self._host.remove_runtime(zone_id)
        await self._store.delete_assignment(zone_id)
        return running.lights

    async def _persist(self, zone_id: str) -> None:
        running = self._running[zone_id]
        await self._store.save_assignment(
            Assignment(
                zone_id=zone_id,
                look_id=running.look_id,
                look_json=running.look_json,
                brightness=running.brightness,
                lights=tuple(running.lights),
                started_at=running.since,
            )
        )

    def _info(self, zone_id: str, running: _Running) -> RunningZoneInfo:
        runtime = running.runtime
        if runtime is None:
            return RunningZoneInfo(
                zone_id=zone_id,
                look_id=running.look_id,
                look_name=running.look_name,
                since=running.since,
                brightness=running.brightness,
                lights=tuple(running.lights),
                state="crashed",
                error=running.broken,
            )
        return RunningZoneInfo(
            zone_id=zone_id,
            look_id=running.look_id,
            look_name=running.look_name,
            since=running.since,
            brightness=running.brightness,
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

    async def _sync(self, device_ids: Iterable[str], power_on: Iterable[str] = ()) -> None:
        """Bring each light in line with the zone that owns it, or release it."""
        wanted = set(power_on)
        if self._preview_only:
            self._deferred_power_on |= wanted  # applied when preview-only is turned off
        ids = list(dict.fromkeys(device_ids))
        results = await asyncio.gather(
            *(self._sync_device(d, d in wanted) for d in ids), return_exceptions=True
        )
        for device_id, result in zip(ids, results, strict=True):
            if isinstance(result, Exception):
                logger.opt(exception=result).warning("Couldn't update light {}", device_id)

    async def _sync_device(self, device_id: str, power_on: bool) -> None:
        zone_id = self.owner_of(device_id)
        adapter = self._adapter(device_id)
        if zone_id is None:
            self._routes.set_route(device_id, None)
            self._applied.pop(device_id, None)
            if adapter is not None and not self._preview_only:
                await self._release(device_id, adapter)
            return
        running = self._running[zone_id]
        runtime = running.runtime
        if runtime is None:  # the saved look can't be read: leave the light alone
            self._routes.set_route(device_id, None)
            return
        if (
            self._preview_only  # frames reach the web preview only
            or runtime.crash is not None  # the light holds the last frame
            or adapter is None
            or not adapter.is_connected  # offline: it rejoins when it's back
        ):
            self._routes.set_route(device_id, runtime.route_for(device_id))
            return
        if device_id not in self._power:
            self._power[device_id] = (await self._read(adapter)).power
        if device_id not in self._captured:
            await self._capture(device_id, adapter)
        if power_on and self._power[device_id] is not True:  # off, or it can't say
            await self._switch_on(device_id, adapter)
        if self._power[device_id] is False:  # switched off elsewhere: out until it's back on
            self._routes.set_route(device_id, None)
            self._applied.pop(device_id, None)
            return
        await self._apply(device_id, adapter, running, runtime)
        self._routes.set_route(device_id, runtime.route_for(device_id))

    async def _apply(
        self, device_id: str, adapter: DeviceAdapter, running: _Running, runtime: ZoneRuntime
    ) -> None:
        """Start the light's firmware layer, or get it ready to stream, once per change."""
        claim = runtime.claim_for(device_id)
        key: AppliedKey = (running.epoch, runtime.generation, claim[0].id if claim else None)
        if self._applied.get(device_id) == key:
            return
        if claim is not None:
            layer, effect = claim
            self._routes.set_route(device_id, runtime.route_for(device_id))  # stop frames first
            try:
                await effect.start(adapter, effect.start_params(runtime.brightness))
            except Exception as exc:  # rejected or no answer: stream a copy (spec §8)
                logger.warning(
                    "{} didn't start {} ({}); streaming a copy instead",
                    adapter.device_info.name,
                    effect.display_name,
                    exc,
                )
                runtime.mark_emulated(device_id)
                claim = None
                key = (running.epoch, runtime.generation, None)
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

    async def _capture(self, device_id: str, adapter: DeviceAdapter) -> None:
        """Capture a light before dj-ledfx first changes it (spec §4.3)."""
        try:
            state = await adapter.capture_state()
        except Exception as exc:
            logger.warning("Couldn't capture {}: {}", adapter.device_info.name, exc)
            state = None
        if state is None:
            logger.info("{} can't be captured; Off will leave it alone", adapter.device_info.name)
        self._captured[device_id] = state or b""
        await self._db.save_device_state(device_id, state or b"")

    async def _switch_on(self, device_id: str, adapter: DeviceAdapter) -> None:
        """Only ever called for a look being applied (spec §6.4)."""
        try:
            await adapter.set_power(True)
        except Exception as exc:
            logger.warning("Couldn't switch on {}: {}", adapter.device_info.name, exc)
            return
        self._power[device_id] = True

    async def _release(self, device_id: str, adapter: DeviceAdapter) -> None:
        """Put a light back how it was before dj-ledfx took control, once (spec §4.3)."""
        state = self._captured.get(device_id)
        if state is None or not adapter.is_connected:
            return  # nothing to release, or offline: released when it's back
        if state and self._power.get(device_id) is not False:  # never switch a light on
            try:
                await adapter.restore_state(state)
            except Exception as exc:
                logger.warning("Couldn't restore {}: {}", adapter.device_info.name, exc)
                return
            self._power.pop(device_id, None)  # the restore may have switched it off
        del self._captured[device_id]
        await self._db.delete_device_state(device_id)
