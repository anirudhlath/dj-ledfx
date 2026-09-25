"""Zones and assignments in state.db, and the one-off scene migration (spec §6.5, §7.1)."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from loguru import logger

from dj_ledfx.timing import as_utc, utcnow
from dj_ledfx.zones.model import (
    ALL_LIGHTS_ZONE_ID,
    DERIVED_KINDS,
    RECENT_LIMIT,
    Assignment,
    StoppedLook,
    ZoneKind,
    ZoneRecord,
)

if TYPE_CHECKING:
    from dj_ledfx.persistence.state_db import StateDB

Statement = tuple[str, tuple[Any, ...]]

_MIGRATED_KEY = "scenes_migrated"


def new_group_id() -> str:
    return f"group-{uuid.uuid4().hex[:8]}"


def _lights(text: str, zone_id: str) -> tuple[str, ...]:
    try:
        value = json.loads(text)
    except ValueError:
        value = None
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        logger.warning("Zone {}: saved lights are unreadable; using the zone's lights", zone_id)
        return ()
    return tuple(value)


def _time(text: str, zone_id: str) -> datetime:
    try:
        value = datetime.fromisoformat(text)
    except ValueError:
        logger.warning("Zone {}: unreadable start time {!r}; using now", zone_id, text)
        return utcnow()
    return as_utc(value)


def _utc(when: datetime) -> str:
    """A time as UTC text, so that recent_looks' text compares as the times do."""
    return as_utc(when).astimezone(UTC).isoformat()


class ZoneStore:
    def __init__(self, db: StateDB) -> None:
        self._db = db

    async def load_zones(self) -> list[ZoneRecord]:
        zones = await self._db.fetch_all(
            "SELECT id, name, kind, all_lights FROM zones ORDER BY rowid"
        )
        members = await self._db.fetch_all(
            "SELECT zone_id, device_id FROM zone_members ORDER BY zone_id, position"
        )
        lights: dict[str, list[str]] = {}
        for zone_id, device_id in members:
            lights.setdefault(zone_id, []).append(device_id)
        return [
            ZoneRecord(
                id=zone_id,
                name=name,
                kind=cast(ZoneKind, kind),
                lights=tuple(lights.get(zone_id, ())),
                all_lights=bool(all_lights),
            )
            for zone_id, name, kind, all_lights in zones
        ]

    async def save_zone(self, zone: ZoneRecord) -> None:
        await self._db.write_many(self._zone_statements(zone))

    async def delete_zone(self, zone_id: str) -> None:
        """Delete a zone; its members and assignment go with it (FK cascade), and its
        recent looks, so a zone made again under its id starts with none."""
        await self._db.write_many(self._delete_statements(zone_id))

    async def sync_derived(self, zones: Sequence[ZoneRecord]) -> None:
        """Make state.db's rooms, sub-zones and whole home match the map's, in one
        transaction. A derived zone the map no longer has is deleted, and its assignment
        with it (FK cascade). Derived zones keep no members: the map says which lights
        they hold."""
        marks = ", ".join("?" for _ in DERIVED_KINDS)
        rows = await self._db.fetch_all(
            f"SELECT id FROM zones WHERE kind IN ({marks})", DERIVED_KINDS
        )
        wanted = {zone.id for zone in zones}
        statements: list[Statement] = [
            statement
            for (zone_id,) in rows
            if zone_id not in wanted
            for statement in self._delete_statements(zone_id)
        ]
        for zone in zones:
            statements += self._zone_statements(replace(zone, lights=(), all_lights=False))
        if statements:
            await self._db.write_many(statements)

    async def load_assignments(self) -> list[Assignment]:
        """Every saved assignment, oldest first, so resuming replays take-overs in order."""
        rows = await self._db.fetch_all(
            "SELECT zone_id, look_id, look, brightness, lights, started_at FROM zone_assignments"
        )
        assignments = [
            Assignment(
                zone_id=zone_id,
                look_id=look_id,
                look_json=look_json,
                brightness=float(brightness),
                lights=_lights(lights_json, zone_id),
                started_at=_time(started_at, zone_id),
            )
            for zone_id, look_id, look_json, brightness, lights_json, started_at in rows
        ]
        return sorted(assignments, key=lambda a: (a.started_at, a.zone_id))

    async def save_assignment(
        self, assignment: Assignment, *, stopped: Iterable[StoppedLook] = ()
    ) -> None:
        """Save a zone's assignment, and remember the looks that stopped for it (a new
        look replacing the one it ran), in one transaction."""
        await self._db.write_many(
            [self._assignment_statement(assignment), *self._remember_statements(stopped)]
        )

    async def delete_assignments(
        self, zone_ids: Iterable[str], *, stopped: Iterable[StoppedLook] = ()
    ) -> None:
        """Forget zones' assignments, and remember the looks that stopped with them, in one
        transaction."""
        statements: list[Statement] = [
            ("DELETE FROM zone_assignments WHERE zone_id=?", (zone_id,)) for zone_id in zone_ids
        ]
        statements += self._remember_statements(stopped)
        if statements:
            await self._db.write_many(statements)

    async def remember(self, stopped: Iterable[StoppedLook]) -> None:
        """Remember looks that stopped, for "Start again" (ruling 19)."""
        statements = self._remember_statements(stopped)
        if statements:
            await self._db.write_many(statements)

    async def load_recent(self) -> list[StoppedLook]:
        """The remembered looks, the newest stop first; of two stopped together, the newer
        start first."""
        rows = await self._db.fetch_all(
            "SELECT zone_id, look_id, started_at, stopped_at FROM recent_looks"
        )
        recent: list[StoppedLook] = []
        for zone_id, look_id, started_at, stopped_at in rows:
            try:
                started = datetime.fromisoformat(started_at)
                stopped = datetime.fromisoformat(stopped_at)
            except ValueError:
                logger.warning("Zone {}: unreadable times for look {}; left out", zone_id, look_id)
                continue
            recent.append(StoppedLook(zone_id, look_id, as_utc(started), as_utc(stopped)))
        return sorted(recent, key=lambda entry: (entry.stopped_at, entry.started_at), reverse=True)

    async def migrate_scenes_once(self) -> None:
        """Turn each scene into a device-group zone, once (spec §6.5). Nothing runs after."""
        done = await self._db.fetch_all(
            "SELECT 1 FROM config WHERE section='_meta' AND key=?", (_MIGRATED_KEY,)
        )
        if done:
            return
        scenes = await self._db.fetch_all("SELECT id, name FROM scenes ORDER BY rowid")
        placements = await self._db.fetch_all(
            "SELECT scene_id, device_id, position_x, position_y, position_z FROM scene_placements"
        )
        by_scene: dict[str, list[tuple[float, float, float, str]]] = {}
        for scene_id, device_id, x, y, z in placements:
            by_scene.setdefault(scene_id, []).append((x, y, z, device_id))
        zones = [
            ZoneRecord(
                id=new_group_id(),
                name=name,
                lights=tuple(device for *_, device in sorted(by_scene.get(scene_id, []))),
                all_lights=not by_scene.get(scene_id),
            )
            for scene_id, name in scenes
        ]
        if not zones:
            zones = [ZoneRecord(id=ALL_LIGHTS_ZONE_ID, name="All lights", all_lights=True)]
        statements = [statement for zone in zones for statement in self._zone_statements(zone)]
        statements.append(
            (
                "INSERT INTO config (section, key, value) VALUES ('_meta', ?, '1') "
                "ON CONFLICT(section, key) DO UPDATE SET value=excluded.value",
                (_MIGRATED_KEY,),
            )
        )
        await self._db.write_many(statements)
        logger.info("Migrated {} scene(s) to {} zone(s)", len(scenes), len(zones))

    @staticmethod
    def _assignment_statement(assignment: Assignment) -> Statement:
        return (
            "INSERT INTO zone_assignments "
            "(zone_id, look_id, look, brightness, lights, started_at) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(zone_id) DO UPDATE SET look_id=excluded.look_id, look=excluded.look, "
            "brightness=excluded.brightness, lights=excluded.lights, "
            "started_at=excluded.started_at",
            (
                assignment.zone_id,
                assignment.look_id,
                assignment.look_json,
                assignment.brightness,
                json.dumps(list(assignment.lights)),
                assignment.started_at.isoformat(),
            ),
        )

    @staticmethod
    def _remember_statements(stopped: Iterable[StoppedLook]) -> list[Statement]:
        """Each zone and look keeps its newest stop, and only the RECENT_LIMIT newest stay.
        No statements when nothing stopped."""
        statements: list[Statement] = [
            (
                "INSERT INTO recent_looks (zone_id, look_id, started_at, stopped_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(zone_id, look_id) DO UPDATE SET started_at=excluded.started_at, "
                "stopped_at=excluded.stopped_at "
                "WHERE excluded.stopped_at >= recent_looks.stopped_at",
                (entry.zone_id, entry.look_id, _utc(entry.started_at), _utc(entry.stopped_at)),
            )
            for entry in stopped
        ]
        if statements:
            statements.append(
                (
                    "DELETE FROM recent_looks WHERE rowid NOT IN (SELECT rowid FROM recent_looks "
                    "ORDER BY stopped_at DESC, started_at DESC LIMIT ?)",
                    (RECENT_LIMIT,),
                )
            )
        return statements

    @staticmethod
    def _delete_statements(zone_id: str) -> list[Statement]:
        """recent_looks has no foreign key (migration 006), so its rows go by hand."""
        return [
            ("DELETE FROM zones WHERE id=?", (zone_id,)),
            ("DELETE FROM recent_looks WHERE zone_id=?", (zone_id,)),
        ]

    @staticmethod
    def _zone_statements(zone: ZoneRecord) -> list[Statement]:
        statements: list[Statement] = [
            (
                "INSERT INTO zones (id, name, kind, all_lights) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name, kind=excluded.kind, "
                "all_lights=excluded.all_lights",
                (zone.id, zone.name, zone.kind, int(zone.all_lights)),
            ),
            ("DELETE FROM zone_members WHERE zone_id=?", (zone.id,)),
        ]
        statements += [
            (
                "INSERT INTO zone_members (zone_id, device_id, position) VALUES (?, ?, ?)",
                (zone.id, device_id, position),
            )
            for position, device_id in enumerate(zone.lights)
        ]
        return statements
