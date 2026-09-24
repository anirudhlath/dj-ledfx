from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest_asyncio

from dj_ledfx.persistence.state_db import StateDB
from dj_ledfx.zones.model import ALL_LIGHTS_ZONE_ID, Assignment, ZoneRecord
from dj_ledfx.zones.store import ZoneStore, new_group_id


@pytest_asyncio.fixture
async def db(tmp_path: Path) -> AsyncIterator[StateDB]:
    state_db = StateDB(tmp_path / "state.db")
    await state_db.open()
    yield state_db
    await state_db.close()


async def test_zones_keep_their_light_order(db: StateDB) -> None:
    store = ZoneStore(db)
    await store.save_zone(ZoneRecord(id="desk", name="Office desk", lights=("c", "a", "b")))
    await store.save_zone(ZoneRecord(id="all", name="Everything", all_lights=True))
    assert await store.load_zones() == [
        ZoneRecord(id="desk", name="Office desk", lights=("c", "a", "b")),
        ZoneRecord(id="all", name="Everything", all_lights=True),
    ]


async def test_saving_a_zone_replaces_its_lights(db: StateDB) -> None:
    store = ZoneStore(db)
    await store.save_zone(ZoneRecord(id="desk", name="Desk", lights=("a", "b")))
    await store.save_zone(ZoneRecord(id="desk", name="Desk 2", lights=("b",)))
    assert await store.load_zones() == [ZoneRecord(id="desk", name="Desk 2", lights=("b",))]


async def test_assignments_round_trip_oldest_first(db: StateDB) -> None:
    store = ZoneStore(db)
    await store.save_zone(ZoneRecord(id="a", name="A", lights=("x",)))
    await store.save_zone(ZoneRecord(id="b", name="B", lights=("y",)))
    newer = Assignment("a", "firmware", "{}", 0.5, ("x",), datetime(2026, 9, 24, 20, tzinfo=UTC))
    older = Assignment(
        "b", "classic-breathe", "{}", 1.0, ("y",), datetime(2026, 9, 24, 19, tzinfo=UTC)
    )
    await store.save_assignment(newer)
    await store.save_assignment(older)
    assert await store.load_assignments() == [older, newer]

    await store.save_assignment(Assignment("a", "firmware", "{}", 0.25, (), newer.started_at))
    await store.delete_assignment("b")
    assert [(a.zone_id, a.brightness) for a in await store.load_assignments()] == [("a", 0.25)]

    await store.delete_zone("a")
    assert await store.load_assignments() == []
    assert [zone.id for zone in await store.load_zones()] == ["b"]


async def test_scenes_become_device_group_zones_once(db: StateDB) -> None:
    for device_id in ("lifx:a", "lifx:b", "lifx:c"):
        await db.upsert_device({"id": device_id, "name": device_id, "backend": "lifx"})
    await db.save_scene({"id": "s1", "name": "Desk", "is_active": 1})
    await db.save_scene({"id": "s2", "name": "Default"})
    await db.save_placement({"scene_id": "s1", "device_id": "lifx:b", "position_x": 2.0})
    await db.save_placement({"scene_id": "s1", "device_id": "lifx:a", "position_x": 1.0})
    await db.save_placement(
        {"scene_id": "s1", "device_id": "lifx:c", "position_x": 1.0, "position_y": 1.0}
    )
    store = ZoneStore(db)

    await store.migrate_scenes_once()

    zones = await store.load_zones()
    assert [(z.name, z.kind, z.lights, z.all_lights) for z in zones] == [
        ("Desk", "group", ("lifx:a", "lifx:c", "lifx:b"), False),
        ("Default", "group", (), True),
    ]
    assert all(zone.id.startswith("group-") for zone in zones)
    assert await store.load_assignments() == []  # nothing runs after the migration

    await store.delete_zone(zones[0].id)
    await store.migrate_scenes_once()
    assert [z.name for z in await store.load_zones()] == ["Default"]


async def test_no_scenes_gives_one_all_lights_zone(db: StateDB) -> None:
    store = ZoneStore(db)
    await store.migrate_scenes_once()
    assert await store.load_zones() == [
        ZoneRecord(id=ALL_LIGHTS_ZONE_ID, name="All lights", all_lights=True)
    ]


def test_group_ids() -> None:
    first, second = new_group_id(), new_group_id()
    assert first.startswith("group-") and len(first) == len("group-") + 8
    assert first != second
