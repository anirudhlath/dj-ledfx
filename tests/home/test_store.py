from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from conftest import as_schema
from loguru import logger

from dj_ledfx.home.seed import seed_home
from dj_ledfx.home.shapes import LineShape, Placement, PointShape
from dj_ledfx.home.store import HomeStore, ScenePlacement
from dj_ledfx.persistence.state_db import StateDB

LAMP = Placement(
    PointShape((1.0, 2.0, 0.5)),
    "",
    confirmed=True,
    confirmed_at=datetime(2026, 9, 24, 19, 0, tzinfo=UTC),
)
ROPE = Placement(LineShape(((0.0, 0.0, 2.0), (2.0, 0.0, 2.0))), "reverse-path")


async def test_migration_005_adds_the_map_and_the_placements(db: StateDB) -> None:
    assert await db.get_schema_version() >= 5
    columns = [row[1] for row in await db.fetch_all("PRAGMA table_info(placements)")]
    assert columns == [
        "target_id",
        "shape",
        "led_order",
        "confirmed",
        "confirmed_at",
        "updated_at",
        "source",  # 009
    ]


async def test_the_map_is_seeded_on_first_use_and_kept(db: StateDB) -> None:
    store = HomeStore(db)
    home = await store.load_home()
    assert home == seed_home()

    taller = replace(home, ceiling=home.ceiling + 0.5)
    await store.save_home(taller)

    assert await HomeStore(db).load_home() == taller


async def test_an_unreadable_map_falls_back_to_the_seed_and_is_kept_for_repair(
    db: StateDB,
) -> None:
    store = HomeStore(db)
    await store.load_home()
    await db.write("UPDATE home_map SET body='{\"rooms\": []}' WHERE id=1")
    warnings: list[str] = []
    sink = logger.add(lambda message: warnings.append(str(message)), level="WARNING")
    try:
        assert await store.load_home() == seed_home()
    finally:
        logger.remove(sink)

    assert await db.fetch_all("SELECT body FROM home_map") == [('{"rooms": []}',)]
    assert await db.fetch_all("SELECT body FROM home_map_unreadable") == [('{"rooms": []}',)]
    assert any("home_map_unreadable" in warning for warning in warnings)

    await store.save_home(replace(seed_home(), ceiling=3.1))  # the first edit

    kept = await db.fetch_all("SELECT body FROM home_map_unreadable")
    assert kept == [('{"rooms": []}',)]  # the edit replaced the map, not the copy


async def test_placements_are_saved_changed_and_removed(db: StateDB) -> None:
    store = HomeStore(db)
    await store.save_placement("lamp-1", LAMP)
    await store.save_placement("rope-1", ROPE)
    await store.save_placement("rope-1", replace(ROPE, confirmed=True))

    assert await store.load_placements() == {
        "lamp-1": LAMP,
        "rope-1": replace(ROPE, confirmed=True),
    }

    await store.delete_placement("lamp-1")
    assert list(await store.load_placements()) == ["rope-1"]


async def test_placements_keep_where_they_came_from(db: StateDB) -> None:
    store = HomeStore(db)
    bulb = Placement(PointShape((0.0, 0.0, 1.0)), "")
    placed = {"lamp-1": replace(LAMP, source="owner"), "rope-1": replace(ROPE, source="seed")}

    await store.save_placements({**placed, "bulb": bulb})

    assert await store.load_placements() == {**placed, "bulb": bulb}
    assert bulb.source == "guess"  # what a placement is unless it says


@pytest.mark.parametrize(
    ("seeded", "sources"),
    [
        (True, {"lamp": "seed", "tile": "owner", "moved": "guess"}),
        (False, {"lamp": "guess", "tile": "guess", "moved": "guess"}),
    ],
)
async def test_schema_9_gives_each_placement_made_before_it_a_source(
    tmp_path: Path, seeded: bool, sources: dict[str, str]
) -> None:
    """A row from before placements.source is a guess, except the first start's: the
    seeding's rows, all written within a second, are seed, or owner where an old scene
    placed the light."""
    path = tmp_path / "state.db"
    db = StateDB(path)
    await db.open()
    await as_schema(db, 8)
    point = json.dumps({"kind": "point", "position": [1.0, 2.0, 1.0]})
    for target, at in (
        ("lamp", "2026-09-30T12:00:00.000100+00:00"),
        ("tile", "2026-09-30T12:00:00.000200+00:00"),
        ("moved", "2026-09-30T18:30:00.500000+00:00"),
    ):
        await db.write(
            "INSERT INTO placements (target_id, shape, updated_at) VALUES (?, ?, ?)",
            (target, point, at),
        )
    if seeded:
        await db.write(*StateDB.mark_statement("home_placements_seeded"))
    await db.write("INSERT INTO scenes (id, name) VALUES ('old', 'Old')")
    await db.write("INSERT INTO devices (id, name, backend) VALUES ('tile', 'Tile', 'lifx')")
    await db.write(
        "INSERT INTO scene_placements (scene_id, device_id, geometry_type) "
        "VALUES ('old', 'tile', 'matrix')"
    )
    await db.close()

    db = StateDB(path)
    await db.open()
    try:
        version = await db.get_schema_version()
        placements = await HomeStore(db).load_placements()
    finally:
        await db.close()

    assert version == 10
    assert {target: placement.source for target, placement in placements.items()} == sources


async def test_an_unreadable_placement_is_left_out(db: StateDB) -> None:
    store = HomeStore(db)
    await store.save_placement("lamp-1", LAMP)
    await db.write(
        "INSERT INTO placements (target_id, shape, led_order, confirmed, updated_at) "
        "VALUES ('bad', '{\"kind\": \"blob\"}', '', 0, '')"
    )

    assert list(await store.load_placements()) == ["lamp-1"]


async def test_placements_are_seeded_once_with_the_mark(db: StateDB) -> None:
    store = HomeStore(db)
    assert not await store.placements_seeded()

    await store.mark_placements_seeded({"lamp-1": LAMP})

    assert await store.placements_seeded()
    assert await store.load_placements() == {"lamp-1": LAMP}


async def test_the_old_scene_placements_are_read_in_the_scene_editors_axes(db: StateDB) -> None:
    await db.upsert_device({"id": "strip-1", "name": "Strip", "backend": "govee"})
    await db.save_scene({"id": "s1", "name": "Scene"})
    await db.save_placement(
        {
            "scene_id": "s1",
            "device_id": "strip-1",
            "position_x": 1.0,
            "position_y": 2.0,
            "position_z": 3.0,
            "geometry_type": "strip",
            "direction_x": 1.0,
            "direction_y": 0.0,
            "direction_z": 0.0,
            "length": 1.5,
        }
    )

    assert await HomeStore(db).load_scene_placements() == [
        ScenePlacement("s1", "strip-1", (1.0, 2.0, 3.0), "strip", (1.0, 0.0, 0.0), 1.5, None, None)
    ]
