from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from dj_ledfx.persistence.state_db import StateDB
from dj_ledfx.zones.model import (
    ALL_LIGHTS_ZONE_ID,
    RECENT_LIMIT,
    Assignment,
    StoppedLook,
    ZoneRecord,
)
from dj_ledfx.zones.store import ZoneStore, new_group_id


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
    await store.delete_assignments(["b"])
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


async def test_derived_zones_follow_the_map_and_take_their_assignments_with_them(
    db: StateDB,
) -> None:
    store = ZoneStore(db)
    group = ZoneRecord(id="group-1", name="Shelf", lights=("a",))
    await store.save_zone(group)
    rooms = [
        ZoneRecord("home", "Whole home", "home"),
        ZoneRecord("west", "West", "room", lights=("ignored",)),
        ZoneRecord("desk", "Desk", "sub-zone"),
    ]
    await store.sync_derived(rooms)
    await store.save_assignment(
        Assignment("desk", "classic-breathe", "{}", 1.0, ("a",), datetime(2026, 9, 24, tzinfo=UTC))
    )

    await store.sync_derived(rooms[:2])

    zones = {zone.id: (zone.kind, zone.lights) for zone in await store.load_zones()}
    assert zones == {"group-1": ("group", ("a",)), "home": ("home", ()), "west": ("room", ())}
    assert await store.load_assignments() == []  # the desk's went with it


async def test_migration_006_adds_the_recent_looks(db: StateDB) -> None:
    assert await db.get_schema_version() >= 6
    columns = [row[1] for row in await db.fetch_all("PRAGMA table_info(recent_looks)")]
    assert columns == ["zone_id", "look_id", "started_at", "stopped_at"]


async def test_each_zone_and_look_keeps_its_newest_stop_compared_in_utc(db: StateDB) -> None:
    store = ZoneStore(db)
    at = datetime(2026, 9, 24, 19, 0, tzinfo=UTC)
    half_past = datetime(2026, 9, 24, 21, 30, tzinfo=timezone(timedelta(hours=2)))  # 19:30 UTC
    newest = StoppedLook("desk", "classic-breathe", at, at + timedelta(minutes=45))

    await store.remember([StoppedLook("desk", "classic-breathe", at, half_past)])
    await store.remember([newest])
    await store.remember([StoppedLook("desk", "classic-breathe", at, at + timedelta(minutes=10))])

    assert await store.load_recent() == [newest]


async def test_only_the_newest_stops_are_kept(db: StateDB) -> None:
    store = ZoneStore(db)
    at = datetime(2026, 9, 24, 19, 0, tzinfo=UTC)
    minute = timedelta(minutes=1)
    await store.remember(
        [StoppedLook(f"zone-{n}", "classic-strobe", at, at + n * minute) for n in range(12)]
    )
    await store.remember(
        [StoppedLook("late", "classic-strobe", at + 11 * minute, at + 11 * minute)]
    )

    recent = await store.load_recent()

    assert len(recent) == RECENT_LIMIT
    assert [entry.zone_id for entry in recent] == [
        "late",  # it stopped with zone-11 but started later
        *(f"zone-{n}" for n in range(11, 2, -1)),
    ]


async def test_a_deleted_zone_forgets_its_recent_looks(db: StateDB) -> None:
    store = ZoneStore(db)
    await store.save_zone(ZoneRecord(id="shelf", name="Shelf", lights=("b",)))
    derived = [ZoneRecord("west", "West", "room"), ZoneRecord("desk", "Desk", "sub-zone")]
    await store.sync_derived(derived)
    at = datetime(2026, 9, 24, 19, 0, tzinfo=UTC)
    await store.remember(
        [StoppedLook(zone, "classic-breathe", at, at) for zone in ("west", "desk", "shelf")]
    )

    await store.sync_derived(derived[:1])  # the desk is gone from the map
    await store.delete_zone("shelf")

    assert [entry.zone_id for entry in await store.load_recent()] == ["west"]
