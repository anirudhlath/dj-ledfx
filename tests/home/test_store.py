from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest_asyncio
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


@pytest_asyncio.fixture
async def db(tmp_path: Path) -> AsyncIterator[StateDB]:
    state_db = StateDB(tmp_path / "state.db")
    await state_db.open()
    yield state_db
    await state_db.close()


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
        ScenePlacement(
            "s1", "strip-1", (1.0, 2.0, 3.0), "strip", (1.0, 0.0, 0.0), 1.5, None, None, None
        )
    ]
