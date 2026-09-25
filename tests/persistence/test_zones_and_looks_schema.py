from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio

from dj_ledfx.persistence.state_db import StateDB


@pytest_asyncio.fixture
async def db(tmp_path: Path) -> AsyncIterator[StateDB]:
    state_db = StateDB(tmp_path / "state.db")
    await state_db.open()
    yield state_db
    await state_db.close()


async def test_schema_version_is_5(db: StateDB) -> None:
    assert await db.get_schema_version() == 5


async def test_new_tables_exist(db: StateDB) -> None:
    rows = await db.fetch_all("SELECT name FROM sqlite_master WHERE type='table'")
    assert {"zones", "zone_members", "looks", "look_stars", "zone_assignments"} <= {
        row[0] for row in rows
    }


async def test_deleting_a_zone_removes_its_members_and_assignment(db: StateDB) -> None:
    await db.write_many(
        [
            ("INSERT INTO zones (id, name) VALUES (?, ?)", ("z1", "Desk")),
            (
                "INSERT INTO zone_members (zone_id, device_id, position) VALUES (?, ?, ?)",
                ("z1", "lifx:aa", 0),
            ),
            (
                "INSERT INTO zone_assignments "
                "(zone_id, look_id, look, brightness, lights, started_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("z1", "firmware", "{}", 1.0, "[]", "2026-09-24T00:00:00+00:00"),
            ),
        ]
    )
    await db.write("DELETE FROM zones WHERE id=?", ("z1",))
    assert await db.fetch_all("SELECT * FROM zone_members") == []
    assert await db.fetch_all("SELECT * FROM zone_assignments") == []


async def test_write_many_is_one_transaction(db: StateDB) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        await db.write_many(
            [
                ("INSERT INTO zones (id, name) VALUES (?, ?)", ("z1", "Desk")),
                ("INSERT INTO zones (id, name) VALUES (?, ?)", ("z1", "Again")),
            ]
        )
    assert await db.fetch_all("SELECT id FROM zones") == []


async def test_delete_device_state(db: StateDB) -> None:
    await db.save_device_states({"lifx:aa": b"x"})
    await db.delete_device_states(["lifx:aa"])
    assert await db.load_device_state("lifx:aa") is None


async def test_upgrade_clears_what_the_old_transport_left(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    db = StateDB(path)
    await db.open()
    await db.save_device_states({"lifx:aa": b"old"})
    await db.save_config_key("engine", "unassigned_device_mode", '"idle"')
    await db.save_config_key("engine", "fps", "60")
    await db.write("UPDATE config SET value='3' WHERE section='_meta' AND key='schema_version'")
    await db.close()

    db = StateDB(path)
    await db.open()
    try:
        assert await db.get_schema_version() == 5
        assert await db.load_all_device_states() == {}
        assert await db.load_config("engine") == {"fps": "60"}
    finally:
        await db.close()
