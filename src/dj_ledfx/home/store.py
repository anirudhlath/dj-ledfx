"""The home map and the placements in state.db (spec §6.2), and the old scene placements
that M2 moves onto the map once (spec §6.5)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from loguru import logger

from dj_ledfx.home.model import Home, Vec3, home_from_dict, home_to_dict
from dj_ledfx.home.seed import seed_home
from dj_ledfx.home.shapes import Placement, check_led_order, shape_from_dict, shape_to_dict
from dj_ledfx.timing import as_utc, utcnow

if TYPE_CHECKING:
    from dj_ledfx.persistence.state_db import StateDB

Statement = tuple[str, tuple[Any, ...]]

_SEEDED_KEY = "home_placements_seeded"


@dataclass(frozen=True, slots=True)
class ScenePlacement:
    """One device in one of the old scenes, in the scene editor's axes (y up)."""

    scene_id: str
    device_id: str
    position: Vec3
    geometry: str  # point, strip or matrix
    direction: Vec3 | None
    length: float | None
    width: float | None
    rows: int | None
    cols: int | None


def _placement_statement(target_id: str, placement: Placement) -> Statement:
    confirmed_at = placement.confirmed_at.isoformat() if placement.confirmed_at else None
    return (
        "INSERT INTO placements "
        "(target_id, shape, led_order, confirmed, confirmed_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(target_id) DO UPDATE SET "
        "shape=excluded.shape, led_order=excluded.led_order, confirmed=excluded.confirmed, "
        "confirmed_at=excluded.confirmed_at, updated_at=excluded.updated_at",
        (
            target_id,
            json.dumps(shape_to_dict(placement.shape)),
            placement.led_order,
            int(placement.confirmed),
            confirmed_at,
            utcnow().isoformat(),
        ),
    )


def _vec(x: Any, y: Any, z: Any) -> Vec3 | None:
    if x is None or y is None or z is None:
        return None
    return (float(x), float(y), float(z))


class HomeStore:
    def __init__(self, db: StateDB) -> None:
        self._db = db

    # --- the map ---------------------------------------------------------------------

    async def load_home(self) -> Home:
        """The saved map, seeded on first use. An unreadable one is copied aside into
        home_map_unreadable, which backups carry, so the first edit can't lose it, and the
        seed map stands in (spec §8: never crash on a bad map)."""
        rows = await self._db.fetch_all("SELECT body FROM home_map WHERE id=1")
        if not rows:
            home = seed_home()
            await self.save_home(home)
            logger.info("Home map seeded from the handoff's home.json")
            return home
        body = rows[0][0]
        try:
            return home_from_dict(json.loads(body))
        except ValueError as exc:  # bad JSON or a HomeError
            await self.set_aside_unreadable(body)
            logger.warning(
                "The saved home map is unreadable ({}); using the seed map. The saved one is "
                "kept in state.db's home_map_unreadable for repair",
                exc,
            )
            return seed_home()

    async def set_aside_unreadable(self, body: str, at: str | None = None) -> None:
        await self._db.write(
            "INSERT INTO home_map_unreadable (id, body, set_aside_at) VALUES (1, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET body=excluded.body, "
            "set_aside_at=excluded.set_aside_at",
            (body, at or utcnow().isoformat()),
        )

    async def save_home(self, home: Home) -> None:
        await self._db.write(
            "INSERT INTO home_map (id, body, updated_at) VALUES (1, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET body=excluded.body, updated_at=excluded.updated_at",
            (json.dumps(home_to_dict(home)), utcnow().isoformat()),
        )

    # --- placements ------------------------------------------------------------------

    async def load_placements(self) -> dict[str, Placement]:
        """Every readable placement by target id. An unreadable one is logged and left out,
        so its light is placed again."""
        rows = await self._db.fetch_all(
            "SELECT target_id, shape, led_order, confirmed, confirmed_at FROM placements "
            "ORDER BY target_id"
        )
        placements: dict[str, Placement] = {}
        for target_id, shape_json, led_order, confirmed, confirmed_at in rows:
            try:
                shape = shape_from_dict(json.loads(shape_json))
                order = check_led_order(shape.kind, led_order)
                at = as_utc(datetime.fromisoformat(confirmed_at)) if confirmed_at else None
            except (ValueError, TypeError) as exc:
                logger.warning("Light {}: its saved placement is unreadable ({})", target_id, exc)
                continue
            placements[target_id] = Placement(shape, order, bool(confirmed), at)
        return placements

    async def save_placement(self, target_id: str, placement: Placement) -> None:
        sql, params = _placement_statement(target_id, placement)
        await self._db.write(sql, params)

    async def delete_placement(self, target_id: str) -> None:
        await self._db.write("DELETE FROM placements WHERE target_id=?", (target_id,))

    async def placements_seeded(self) -> bool:
        rows = await self._db.fetch_all(
            "SELECT 1 FROM config WHERE section='_meta' AND key=?", (_SEEDED_KEY,)
        )
        return bool(rows)

    async def mark_placements_seeded(self, placements: Mapping[str, Placement]) -> None:
        """Save the first placements and the mark that they were made, as one transaction,
        so a crash between the two can't seed twice."""
        statements = [
            _placement_statement(target, placement) for target, placement in placements.items()
        ]
        statements.append(
            (
                "INSERT INTO config (section, key, value) VALUES ('_meta', ?, '1') "
                "ON CONFLICT(section, key) DO UPDATE SET value=excluded.value",
                (_SEEDED_KEY,),
            )
        )
        await self._db.write_many(statements)

    # --- the old scenes --------------------------------------------------------------

    async def load_scene_placements(self) -> list[ScenePlacement]:
        rows = await self._db.fetch_all(
            "SELECT scene_id, device_id, position_x, position_y, position_z, geometry_type, "
            "direction_x, direction_y, direction_z, length, width, rows, cols "
            "FROM scene_placements ORDER BY scene_id, device_id"
        )
        return [
            ScenePlacement(
                scene_id=scene_id,
                device_id=device_id,
                position=(float(x), float(y), float(z)),
                geometry=str(geometry),
                direction=_vec(dx, dy, dz),
                length=None if length is None else float(length),
                width=None if width is None else float(width),
                rows=None if rows is None else int(rows),
                cols=None if cols is None else int(cols),
            )
            for (
                scene_id,
                device_id,
                x,
                y,
                z,
                geometry,
                dx,
                dy,
                dz,
                length,
                width,
                rows,
                cols,
            ) in rows
        ]
