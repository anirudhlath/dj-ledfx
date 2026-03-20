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


# --- Task 7: Device CRUD ---


@pytest.mark.asyncio
async def test_load_devices_empty(db):
    devices = await db.load_devices()
    assert devices == []


@pytest.mark.asyncio
async def test_upsert_and_load_device(db):
    await db.upsert_device({
        "id": "lifx:d073d5aabbcc",
        "name": "LIFX Strip",
        "backend": "lifx",
        "led_count": 60,
        "ip": "192.168.1.5",
        "mac": "d073d5aabbcc",
    })
    devices = await db.load_devices()
    assert len(devices) == 1
    assert devices[0]["id"] == "lifx:d073d5aabbcc"
    assert devices[0]["name"] == "LIFX Strip"
    assert devices[0]["backend"] == "lifx"
    assert devices[0]["led_count"] == 60
    assert devices[0]["mac"] == "d073d5aabbcc"


@pytest.mark.asyncio
async def test_upsert_device_updates_existing(db):
    await db.upsert_device({
        "id": "lifx:d073d5aabbcc",
        "name": "LIFX Strip",
        "backend": "lifx",
        "led_count": 60,
        "ip": "192.168.1.5",
        "mac": "d073d5aabbcc",
    })
    await db.upsert_device({
        "id": "lifx:d073d5aabbcc",
        "name": "LIFX Strip (Updated)",
        "backend": "lifx",
        "led_count": 82,
        "ip": "192.168.1.6",
        "mac": "d073d5aabbcc",
    })
    devices = await db.load_devices()
    assert len(devices) == 1
    assert devices[0]["name"] == "LIFX Strip (Updated)"
    assert devices[0]["led_count"] == 82


@pytest.mark.asyncio
async def test_delete_device(db):
    await db.upsert_device({
        "id": "govee:1234",
        "name": "Govee Strip",
        "backend": "govee",
        "led_count": 50,
    })
    await db.delete_device("govee:1234")
    devices = await db.load_devices()
    assert devices == []


@pytest.mark.asyncio
async def test_update_device_last_seen(db):
    await db.upsert_device({
        "id": "lifx:aabb",
        "name": "Test",
        "backend": "lifx",
        "led_count": 30,
    })
    await db.update_device_last_seen("lifx:aabb", "2026-03-20T10:00:00")
    devices = await db.load_devices()
    assert devices[0]["last_seen"] == "2026-03-20T10:00:00"


@pytest.mark.asyncio
async def test_update_device_latency(db):
    await db.upsert_device({
        "id": "lifx:aabb",
        "name": "Test",
        "backend": "lifx",
        "led_count": 30,
    })
    await db.update_device_latency("lifx:aabb", 45.2)
    devices = await db.load_devices()
    assert abs(devices[0]["last_latency_ms"] - 45.2) < 0.001


# --- Task 8: Groups CRUD ---


@pytest.mark.asyncio
async def test_load_groups_empty(db):
    groups = await db.load_groups()
    assert groups == []


@pytest.mark.asyncio
async def test_save_and_load_group(db):
    await db.save_group("stage-left", "#ff0000")
    groups = await db.load_groups()
    assert len(groups) == 1
    assert groups[0]["name"] == "stage-left"
    assert groups[0]["color"] == "#ff0000"


@pytest.mark.asyncio
async def test_save_group_upsert(db):
    await db.save_group("stage-left", "#ff0000")
    await db.save_group("stage-left", "#00ff00")
    groups = await db.load_groups()
    assert len(groups) == 1
    assert groups[0]["color"] == "#00ff00"


@pytest.mark.asyncio
async def test_delete_group(db):
    await db.save_group("stage-left", "#ff0000")
    await db.delete_group("stage-left")
    groups = await db.load_groups()
    assert groups == []


@pytest.mark.asyncio
async def test_assign_and_load_device_groups(db):
    await db.upsert_device({"id": "lifx:aa", "name": "Test", "backend": "lifx", "led_count": 10})
    await db.save_group("main", "#888888")
    await db.assign_device_group("main", "lifx:aa")
    result = await db.load_device_groups()
    assert result == {"main": ["lifx:aa"]}


@pytest.mark.asyncio
async def test_unassign_device_group(db):
    await db.upsert_device({"id": "lifx:aa", "name": "Test", "backend": "lifx", "led_count": 10})
    await db.save_group("main", "#888888")
    await db.assign_device_group("main", "lifx:aa")
    await db.unassign_device_group("main", "lifx:aa")
    result = await db.load_device_groups()
    assert result == {"main": []}


@pytest.mark.asyncio
async def test_delete_group_cascades_device_groups(db):
    await db.upsert_device({"id": "lifx:aa", "name": "Test", "backend": "lifx", "led_count": 10})
    await db.save_group("main", "#888888")
    await db.assign_device_group("main", "lifx:aa")
    await db.delete_group("main")
    result = await db.load_device_groups()
    assert result == {}


# --- Task 9: Scenes CRUD ---


@pytest.mark.asyncio
async def test_load_scenes_empty(db):
    scenes = await db.load_scenes()
    assert scenes == []


@pytest.mark.asyncio
async def test_save_and_load_scene(db):
    await db.save_scene({
        "id": "dj-booth",
        "name": "DJ Booth",
        "mapping_type": "linear",
        "effect_mode": "independent",
    })
    scenes = await db.load_scenes()
    assert len(scenes) == 1
    assert scenes[0]["id"] == "dj-booth"
    assert scenes[0]["name"] == "DJ Booth"
    assert scenes[0]["mapping_type"] == "linear"
    assert scenes[0]["is_active"] == 0


@pytest.mark.asyncio
async def test_save_scene_upsert(db):
    await db.save_scene({"id": "s1", "name": "Scene 1", "mapping_type": "linear", "effect_mode": "independent"})
    await db.save_scene({"id": "s1", "name": "Scene Updated", "mapping_type": "radial", "effect_mode": "independent"})
    scenes = await db.load_scenes()
    assert len(scenes) == 1
    assert scenes[0]["name"] == "Scene Updated"
    assert scenes[0]["mapping_type"] == "radial"


@pytest.mark.asyncio
async def test_delete_scene(db):
    await db.save_scene({"id": "s1", "name": "Scene 1", "mapping_type": "linear", "effect_mode": "independent"})
    await db.delete_scene("s1")
    scenes = await db.load_scenes()
    assert scenes == []


@pytest.mark.asyncio
async def test_set_scene_active(db):
    await db.save_scene({"id": "s1", "name": "Scene 1", "mapping_type": "linear", "effect_mode": "independent"})
    await db.save_scene({"id": "s2", "name": "Scene 2", "mapping_type": "linear", "effect_mode": "independent"})
    await db.set_scene_active("s1")
    scenes = await db.load_scenes()
    by_id = {s["id"]: s for s in scenes}
    assert by_id["s1"]["is_active"] == 1
    assert by_id["s2"]["is_active"] == 0


@pytest.mark.asyncio
async def test_set_scene_active_deactivates_others(db):
    await db.save_scene({"id": "s1", "name": "S1", "mapping_type": "linear", "effect_mode": "independent"})
    await db.save_scene({"id": "s2", "name": "S2", "mapping_type": "linear", "effect_mode": "independent"})
    await db.set_scene_active("s1")
    await db.set_scene_active("s2")
    scenes = await db.load_scenes()
    by_id = {s["id"]: s for s in scenes}
    assert by_id["s1"]["is_active"] == 0
    assert by_id["s2"]["is_active"] == 1


@pytest.mark.asyncio
async def test_save_and_load_scene_effect_state(db):
    await db.save_scene({"id": "s1", "name": "S1", "mapping_type": "linear", "effect_mode": "independent"})
    await db.save_scene_effect_state("s1", "BeatPulse", '{"gamma": 2.0}')
    state = await db.load_scene_effect_state("s1")
    assert state is not None
    assert state["effect_class"] == "BeatPulse"
    assert state["params"] == '{"gamma": 2.0}'


@pytest.mark.asyncio
async def test_load_scene_effect_state_missing(db):
    await db.save_scene({"id": "s1", "name": "S1", "mapping_type": "linear", "effect_mode": "independent"})
    state = await db.load_scene_effect_state("s1")
    assert state is None


@pytest.mark.asyncio
async def test_save_and_load_placement(db):
    await db.upsert_device({"id": "lifx:aa", "name": "Test", "backend": "lifx", "led_count": 30})
    await db.save_scene({"id": "s1", "name": "S1", "mapping_type": "linear", "effect_mode": "independent"})
    await db.save_placement({
        "scene_id": "s1",
        "device_id": "lifx:aa",
        "position_x": 1.0,
        "position_y": 2.0,
        "position_z": 0.0,
        "geometry_type": "strip",
    })
    placements = await db.load_scene_placements("s1")
    assert len(placements) == 1
    assert placements[0]["device_id"] == "lifx:aa"
    assert placements[0]["position_x"] == 1.0
    assert placements[0]["geometry_type"] == "strip"


@pytest.mark.asyncio
async def test_delete_placement(db):
    await db.upsert_device({"id": "lifx:aa", "name": "Test", "backend": "lifx", "led_count": 30})
    await db.save_scene({"id": "s1", "name": "S1", "mapping_type": "linear", "effect_mode": "independent"})
    await db.save_placement({
        "scene_id": "s1", "device_id": "lifx:aa",
        "position_x": 0.0, "position_y": 0.0, "position_z": 0.0,
        "geometry_type": "point",
    })
    await db.delete_placement("s1", "lifx:aa")
    placements = await db.load_scene_placements("s1")
    assert placements == []


@pytest.mark.asyncio
async def test_delete_scene_cascades_placements(db):
    await db.upsert_device({"id": "lifx:aa", "name": "Test", "backend": "lifx", "led_count": 30})
    await db.save_scene({"id": "s1", "name": "S1", "mapping_type": "linear", "effect_mode": "independent"})
    await db.save_placement({
        "scene_id": "s1", "device_id": "lifx:aa",
        "position_x": 0.0, "position_y": 0.0, "position_z": 0.0,
        "geometry_type": "point",
    })
    await db.delete_scene("s1")
    # placements table should be empty due to CASCADE
    rows = await db._execute_read("SELECT COUNT(*) FROM scene_placements")
    assert rows[0][0] == 0
