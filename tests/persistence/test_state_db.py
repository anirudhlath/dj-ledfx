"""Tests for StateDB — SQLite persistence layer."""
from pathlib import Path

import pytest
import pytest_asyncio

from dj_ledfx.persistence.state_db import StateDB


@pytest_asyncio.fixture
async def db(tmp_path: Path):
    db_path = tmp_path / "state.db"
    state_db = StateDB(db_path)
    await state_db.open()
    yield state_db
    await state_db.close()


@pytest.mark.asyncio
async def test_creates_db_file(tmp_path):
    db_path = tmp_path / "state.db"
    assert not db_path.exists()
    state_db = StateDB(db_path)
    await state_db.open()
    assert db_path.exists()
    await state_db.close()


@pytest.mark.asyncio
async def test_schema_version_is_1(db):
    version = await db.get_schema_version()
    assert version == 1


@pytest.mark.asyncio
async def test_wal_mode_enabled(db):
    mode = await db._execute_read("PRAGMA journal_mode")
    assert mode[0][0] == "wal"


@pytest.mark.asyncio
async def test_foreign_keys_enabled(db):
    result = await db._execute_read("PRAGMA foreign_keys")
    assert result[0][0] == 1


@pytest.mark.asyncio
async def test_tables_created(db):
    rows = await db._execute_read(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    table_names = [r[0] for r in rows]
    expected = [
        "config", "device_groups", "devices", "groups",
        "presets", "scene_effect_state", "scene_placements", "scenes",
    ]
    assert table_names == expected


@pytest.mark.asyncio
async def test_idempotent_open(tmp_path):
    db_path = tmp_path / "state.db"
    db1 = StateDB(db_path)
    await db1.open()
    await db1.close()
    db2 = StateDB(db_path)
    await db2.open()
    version = await db2.get_schema_version()
    assert version == 1
    await db2.close()


# --- Task 6: Config CRUD ---


@pytest.mark.asyncio
async def test_load_config_empty(db):
    result = await db.load_config("engine")
    assert result == {}


@pytest.mark.asyncio
async def test_save_and_load_config_key(db):
    await db.save_config_key("engine", "fps", "60")
    result = await db.load_config("engine")
    assert result == {"fps": "60"}


@pytest.mark.asyncio
async def test_save_config_key_upsert(db):
    await db.save_config_key("engine", "fps", "60")
    await db.save_config_key("engine", "fps", "90")
    result = await db.load_config("engine")
    assert result == {"fps": "90"}


@pytest.mark.asyncio
async def test_save_config_key_multiple_sections(db):
    await db.save_config_key("engine", "fps", "60")
    await db.save_config_key("web", "port", "8080")
    engine = await db.load_config("engine")
    web = await db.load_config("web")
    assert engine == {"fps": "60"}
    assert web == {"port": "8080"}


@pytest.mark.asyncio
async def test_save_config_bulk(db):
    await db.save_config_bulk("effect", {"active": "beat_pulse", "gamma": "2.0"})
    result = await db.load_config("effect")
    assert result == {"active": "beat_pulse", "gamma": "2.0"}


@pytest.mark.asyncio
async def test_save_config_bulk_upserts(db):
    await db.save_config_bulk("effect", {"active": "beat_pulse"})
    await db.save_config_bulk("effect", {"active": "rainbow_wave", "gamma": "2.5"})
    result = await db.load_config("effect")
    assert result["active"] == "rainbow_wave"
    assert result["gamma"] == "2.5"
