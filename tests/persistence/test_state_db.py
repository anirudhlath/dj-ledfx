"""Tests for StateDB — SQLite persistence layer."""

import asyncio
import sqlite3
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
async def test_schema_version_is_3(db):
    version = await db.get_schema_version()
    assert version == 3


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
        "config",
        "device_groups",
        "device_saved_state",
        "devices",
        "groups",
        "presets",
        "scene_effect_state",
        "scene_placements",
        "scenes",
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
    assert version == 3
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
    await db.upsert_device(
        {
            "id": "lifx:d073d5aabbcc",
            "name": "LIFX Strip",
            "backend": "lifx",
            "led_count": 60,
            "ip": "192.168.1.5",
            "mac": "d073d5aabbcc",
        }
    )
    devices = await db.load_devices()
    assert len(devices) == 1
    assert devices[0]["id"] == "lifx:d073d5aabbcc"
    assert devices[0]["name"] == "LIFX Strip"
    assert devices[0]["backend"] == "lifx"
    assert devices[0]["led_count"] == 60
    assert devices[0]["mac"] == "d073d5aabbcc"


@pytest.mark.asyncio
async def test_upsert_device_updates_existing(db):
    await db.upsert_device(
        {
            "id": "lifx:d073d5aabbcc",
            "name": "LIFX Strip",
            "backend": "lifx",
            "led_count": 60,
            "ip": "192.168.1.5",
            "mac": "d073d5aabbcc",
        }
    )
    await db.upsert_device(
        {
            "id": "lifx:d073d5aabbcc",
            "name": "LIFX Strip (Updated)",
            "backend": "lifx",
            "led_count": 82,
            "ip": "192.168.1.6",
            "mac": "d073d5aabbcc",
        }
    )
    devices = await db.load_devices()
    assert len(devices) == 1
    assert devices[0]["name"] == "LIFX Strip (Updated)"
    assert devices[0]["led_count"] == 82


@pytest.mark.asyncio
async def test_delete_device(db):
    await db.upsert_device(
        {
            "id": "govee:1234",
            "name": "Govee Strip",
            "backend": "govee",
            "led_count": 50,
        }
    )
    await db.delete_device("govee:1234")
    devices = await db.load_devices()
    assert devices == []


@pytest.mark.asyncio
async def test_update_device_last_seen(db):
    await db.upsert_device(
        {
            "id": "lifx:aabb",
            "name": "Test",
            "backend": "lifx",
            "led_count": 30,
        }
    )
    await db.update_device_last_seen("lifx:aabb", "2026-03-20T10:00:00")
    devices = await db.load_devices()
    assert devices[0]["last_seen"] == "2026-03-20T10:00:00"


@pytest.mark.asyncio
async def test_update_device_latency(db):
    await db.upsert_device(
        {
            "id": "lifx:aabb",
            "name": "Test",
            "backend": "lifx",
            "led_count": 30,
        }
    )
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
    await db.save_scene(
        {
            "id": "dj-booth",
            "name": "DJ Booth",
            "mapping_type": "linear",
            "effect_mode": "independent",
        }
    )
    scenes = await db.load_scenes()
    assert len(scenes) == 1
    assert scenes[0]["id"] == "dj-booth"
    assert scenes[0]["name"] == "DJ Booth"
    assert scenes[0]["mapping_type"] == "linear"
    assert scenes[0]["is_active"] == 0


@pytest.mark.asyncio
async def test_save_scene_upsert(db):
    await db.save_scene(
        {"id": "s1", "name": "Scene 1", "mapping_type": "linear", "effect_mode": "independent"}
    )
    await db.save_scene(
        {
            "id": "s1",
            "name": "Scene Updated",
            "mapping_type": "radial",
            "effect_mode": "independent",
        }
    )
    scenes = await db.load_scenes()
    assert len(scenes) == 1
    assert scenes[0]["name"] == "Scene Updated"
    assert scenes[0]["mapping_type"] == "radial"


@pytest.mark.asyncio
async def test_delete_scene(db):
    await db.save_scene(
        {"id": "s1", "name": "Scene 1", "mapping_type": "linear", "effect_mode": "independent"}
    )
    await db.delete_scene("s1")
    scenes = await db.load_scenes()
    assert scenes == []


@pytest.mark.asyncio
async def test_set_scene_active(db):
    await db.save_scene(
        {"id": "s1", "name": "Scene 1", "mapping_type": "linear", "effect_mode": "independent"}
    )
    await db.save_scene(
        {"id": "s2", "name": "Scene 2", "mapping_type": "linear", "effect_mode": "independent"}
    )
    await db.set_scene_active("s1")
    scenes = await db.load_scenes()
    by_id = {s["id"]: s for s in scenes}
    assert by_id["s1"]["is_active"] == 1
    assert by_id["s2"]["is_active"] == 0


@pytest.mark.asyncio
async def test_set_scene_active_does_not_deactivate_others(db):
    """Multiple scenes can be active concurrently; set_scene_active only sets one."""
    await db.save_scene(
        {"id": "s1", "name": "S1", "mapping_type": "linear", "effect_mode": "independent"}
    )
    await db.save_scene(
        {"id": "s2", "name": "S2", "mapping_type": "linear", "effect_mode": "independent"}
    )
    await db.set_scene_active("s1")
    await db.set_scene_active("s2")
    scenes = await db.load_scenes()
    by_id = {s["id"]: s for s in scenes}
    # Both scenes should now be active (concurrent multi-scene support)
    assert by_id["s1"]["is_active"] == 1
    assert by_id["s2"]["is_active"] == 1


@pytest.mark.asyncio
async def test_set_scene_inactive(db):
    """set_scene_inactive only deactivates the specified scene."""
    await db.save_scene(
        {"id": "s1", "name": "S1", "mapping_type": "linear", "effect_mode": "independent"}
    )
    await db.save_scene(
        {"id": "s2", "name": "S2", "mapping_type": "linear", "effect_mode": "independent"}
    )
    await db.set_scene_active("s1")
    await db.set_scene_active("s2")
    await db.set_scene_inactive("s1")
    scenes = await db.load_scenes()
    by_id = {s["id"]: s for s in scenes}
    assert by_id["s1"]["is_active"] == 0
    assert by_id["s2"]["is_active"] == 1


@pytest.mark.asyncio
async def test_save_and_load_scene_effect_state(db):
    await db.save_scene(
        {"id": "s1", "name": "S1", "mapping_type": "linear", "effect_mode": "independent"}
    )
    await db.save_scene_effect_state("s1", "BeatPulse", '{"gamma": 2.0}')
    state = await db.load_scene_effect_state("s1")
    assert state is not None
    assert state["effect_class"] == "BeatPulse"
    assert state["params"] == '{"gamma": 2.0}'


@pytest.mark.asyncio
async def test_load_scene_effect_state_missing(db):
    await db.save_scene(
        {"id": "s1", "name": "S1", "mapping_type": "linear", "effect_mode": "independent"}
    )
    state = await db.load_scene_effect_state("s1")
    assert state is None


@pytest.mark.asyncio
async def test_save_and_load_placement(db):
    await db.upsert_device({"id": "lifx:aa", "name": "Test", "backend": "lifx", "led_count": 30})
    await db.save_scene(
        {"id": "s1", "name": "S1", "mapping_type": "linear", "effect_mode": "independent"}
    )
    await db.save_placement(
        {
            "scene_id": "s1",
            "device_id": "lifx:aa",
            "position_x": 1.0,
            "position_y": 2.0,
            "position_z": 0.0,
            "geometry_type": "strip",
        }
    )
    placements = await db.load_scene_placements("s1")
    assert len(placements) == 1
    assert placements[0]["device_id"] == "lifx:aa"
    assert placements[0]["position_x"] == 1.0
    assert placements[0]["geometry_type"] == "strip"


@pytest.mark.asyncio
async def test_delete_placement(db):
    await db.upsert_device({"id": "lifx:aa", "name": "Test", "backend": "lifx", "led_count": 30})
    await db.save_scene(
        {"id": "s1", "name": "S1", "mapping_type": "linear", "effect_mode": "independent"}
    )
    await db.save_placement(
        {
            "scene_id": "s1",
            "device_id": "lifx:aa",
            "position_x": 0.0,
            "position_y": 0.0,
            "position_z": 0.0,
            "geometry_type": "point",
        }
    )
    await db.delete_placement("s1", "lifx:aa")
    placements = await db.load_scene_placements("s1")
    assert placements == []


@pytest.mark.asyncio
async def test_delete_scene_cascades_placements(db):
    await db.upsert_device({"id": "lifx:aa", "name": "Test", "backend": "lifx", "led_count": 30})
    await db.save_scene(
        {"id": "s1", "name": "S1", "mapping_type": "linear", "effect_mode": "independent"}
    )
    await db.save_placement(
        {
            "scene_id": "s1",
            "device_id": "lifx:aa",
            "position_x": 0.0,
            "position_y": 0.0,
            "position_z": 0.0,
            "geometry_type": "point",
        }
    )
    await db.delete_scene("s1")
    # placements table should be empty due to CASCADE
    rows = await db._execute_read("SELECT COUNT(*) FROM scene_placements")
    assert rows[0][0] == 0


# --- Task 10: Presets CRUD ---


@pytest.mark.asyncio
async def test_load_presets_empty(db):
    presets = await db.load_presets()
    assert presets == []


@pytest.mark.asyncio
async def test_save_and_load_preset(db):
    await db.save_preset("My Pulse", "BeatPulse", '{"gamma": 2.0}')
    presets = await db.load_presets()
    assert len(presets) == 1
    assert presets[0]["name"] == "My Pulse"
    assert presets[0]["effect_class"] == "BeatPulse"
    assert presets[0]["params"] == '{"gamma": 2.0}'


@pytest.mark.asyncio
async def test_save_preset_upsert(db):
    await db.save_preset("My Pulse", "BeatPulse", '{"gamma": 2.0}')
    await db.save_preset("My Pulse", "BeatPulse", '{"gamma": 3.5}')
    presets = await db.load_presets()
    assert len(presets) == 1
    assert presets[0]["params"] == '{"gamma": 3.5}'


@pytest.mark.asyncio
async def test_delete_preset(db):
    await db.save_preset("My Pulse", "BeatPulse", '{"gamma": 2.0}')
    await db.delete_preset("My Pulse")
    presets = await db.load_presets()
    assert presets == []


@pytest.mark.asyncio
async def test_multiple_presets(db):
    await db.save_preset("Pulse 1", "BeatPulse", '{"gamma": 2.0}')
    await db.save_preset("Wave 1", "RainbowWave", '{"speed": 1.0}')
    presets = await db.load_presets()
    assert len(presets) == 2
    names = {p["name"] for p in presets}
    assert names == {"Pulse 1", "Wave 1"}


# --- Task 11: Debounced Writes (via DebouncedWriter) ---


@pytest.mark.asyncio
async def test_schedule_latency_coalesces(db):
    """Multiple rapid latency updates coalesce to the last value."""
    from dj_ledfx.persistence.debounced_writer import DebouncedWriter

    writer = DebouncedWriter(db)
    await db.upsert_device({"id": "lifx:aa", "name": "Test", "backend": "lifx", "led_count": 30})
    writer.schedule_latency_update("lifx:aa", 10.0)
    writer.schedule_latency_update("lifx:aa", 20.0)
    writer.schedule_latency_update("lifx:aa", 35.5)
    await writer.flush_pending()
    devices = await db.load_devices()
    assert abs(devices[0]["last_latency_ms"] - 35.5) < 0.001


@pytest.mark.asyncio
async def test_schedule_effect_state_coalesces(db):
    """Multiple rapid effect state updates coalesce to the last value."""
    from dj_ledfx.persistence.debounced_writer import DebouncedWriter

    writer = DebouncedWriter(db)
    await db.save_scene(
        {"id": "s1", "name": "S1", "mapping_type": "linear", "effect_mode": "independent"}
    )
    writer.schedule_effect_state_update("s1", "BeatPulse", '{"gamma": 1.0}')
    writer.schedule_effect_state_update("s1", "BeatPulse", '{"gamma": 2.0}')
    writer.schedule_effect_state_update("s1", "RainbowWave", '{"speed": 0.5}')
    await writer.flush_pending()
    state = await db.load_scene_effect_state("s1")
    assert state is not None
    assert state["effect_class"] == "RainbowWave"
    assert state["params"] == '{"speed": 0.5}'


@pytest.mark.asyncio
async def test_flush_pending_before_close(tmp_path):
    """Pending writes are flushed before closing the DB."""
    from dj_ledfx.persistence.debounced_writer import DebouncedWriter

    db_path = tmp_path / "state.db"
    state_db = StateDB(db_path)
    await state_db.open()
    writer = DebouncedWriter(state_db)
    await state_db.upsert_device(
        {"id": "lifx:aa", "name": "Test", "backend": "lifx", "led_count": 30}
    )
    writer.schedule_latency_update("lifx:aa", 77.7)
    await writer.flush_pending()
    await state_db.close()

    # Re-open and verify the latency was persisted
    state_db2 = StateDB(db_path)
    await state_db2.open()
    devices = await state_db2.load_devices()
    await state_db2.close()
    assert abs(devices[0]["last_latency_ms"] - 77.7) < 0.001


@pytest.mark.asyncio
async def test_schedule_latency_multiple_devices(db):
    """Pending latency updates track multiple device IDs independently."""
    from dj_ledfx.persistence.debounced_writer import DebouncedWriter

    writer = DebouncedWriter(db)
    await db.upsert_device({"id": "lifx:aa", "name": "A", "backend": "lifx", "led_count": 10})
    await db.upsert_device({"id": "lifx:bb", "name": "B", "backend": "lifx", "led_count": 10})
    writer.schedule_latency_update("lifx:aa", 11.1)
    writer.schedule_latency_update("lifx:bb", 22.2)
    await writer.flush_pending()
    devices = await db.load_devices()
    by_id = {d["id"]: d for d in devices}
    assert abs(by_id["lifx:aa"]["last_latency_ms"] - 11.1) < 0.001
    assert abs(by_id["lifx:bb"]["last_latency_ms"] - 22.2) < 0.001


# --- Task 22: First-Launch TOML Migration ---


@pytest.mark.asyncio
async def test_migrate_from_config_toml(tmp_path):
    import json

    import tomli_w

    from dj_ledfx.persistence.toml_io import migrate_from_toml

    config_toml = tmp_path / "config.toml"
    config_data = {
        "engine": {"fps": 90},
        "effect": {
            "active_effect": "beat_pulse",
            "beat_pulse": {"gamma": 3.0, "palette": ["#ff0000"]},
        },
        "network": {"interface": "192.168.1.100"},
    }
    config_toml.write_bytes(tomli_w.dumps(config_data).encode())

    db = StateDB(tmp_path / "state.db")
    await db.open()
    await migrate_from_toml(db, config_path=config_toml)

    engine_cfg = await db.load_config("engine")
    assert engine_cfg.get("fps") == "90"

    network_cfg = await db.load_config("network")
    assert network_cfg.get("interface") == "192.168.1.100"

    scenes = await db.load_scenes()
    assert len(scenes) == 1
    assert scenes[0]["id"] == "default"

    state = await db.load_scene_effect_state("default")
    assert state is not None
    assert state["effect_class"] == "beat_pulse"
    params = json.loads(state["params"])
    assert params["gamma"] == 3.0

    assert not config_toml.exists()
    assert (tmp_path / "config.toml.bak").exists()
    await db.close()


@pytest.mark.asyncio
async def test_migrate_from_presets_toml(tmp_path):
    import json

    import tomli_w

    from dj_ledfx.persistence.toml_io import migrate_from_toml

    presets_toml = tmp_path / "presets.toml"
    presets_data = {
        "presets": {"My Preset": {"effect_class": "beat_pulse", "params": {"gamma": 2.5}}}
    }
    presets_toml.write_bytes(tomli_w.dumps(presets_data).encode())

    db = StateDB(tmp_path / "state.db")
    await db.open()
    await migrate_from_toml(db, presets_path=presets_toml)

    presets = await db.load_presets()
    preset_by_name = {p["name"]: p for p in presets}
    assert "My Preset" in preset_by_name
    params = json.loads(preset_by_name["My Preset"]["params"])
    assert params["gamma"] == 2.5

    assert not presets_toml.exists()
    assert (tmp_path / "presets.toml.bak").exists()
    await db.close()


@pytest.mark.asyncio
async def test_migrate_skips_if_no_toml(tmp_path):
    from dj_ledfx.persistence.toml_io import migrate_from_toml

    db = StateDB(tmp_path / "state.db")
    await db.open()
    await migrate_from_toml(
        db,
        config_path=tmp_path / "config.toml",
        presets_path=tmp_path / "presets.toml",
    )
    engine_cfg = await db.load_config("engine")
    assert engine_cfg == {}
    await db.close()


# --- FK-safe upsert tests ---


@pytest.mark.asyncio
async def test_upsert_device_preserves_group_membership(db):
    """Updating a device via upsert should not cascade-delete its group membership."""
    await db.upsert_device({"id": "d1", "name": "Dev1", "backend": "lifx", "led_count": 10})
    await db.save_group("g1", "#ff0000")
    await db.assign_device_group("g1", "d1")
    # Update the device (e.g. change IP) — must NOT delete the group assignment
    await db.upsert_device(
        {"id": "d1", "name": "Dev1", "backend": "lifx", "led_count": 10, "ip": "1.2.3.4"}
    )
    groups = await db.load_device_groups()
    assert "d1" in groups.get("g1", [])


@pytest.mark.asyncio
async def test_upsert_device_preserves_scene_placements(db):
    """Updating a device via upsert should not cascade-delete its scene placements."""
    await db.upsert_device({"id": "d1", "name": "Dev1", "backend": "lifx", "led_count": 10})
    await db.save_scene(
        {"id": "s1", "name": "Scene 1", "mapping_type": "linear", "effect_mode": "independent"}
    )
    await db.save_placement(
        {
            "scene_id": "s1",
            "device_id": "d1",
            "position_x": 0.0,
            "position_y": 0.0,
            "position_z": 0.0,
            "geometry_type": "strip",
        }
    )
    # Update device with a new IP — must NOT wipe the placement
    await db.upsert_device(
        {"id": "d1", "name": "Dev1", "backend": "lifx", "led_count": 10, "ip": "10.0.0.5"}
    )
    placements = await db.load_scene_placements("s1")
    assert len(placements) == 1
    assert placements[0]["device_id"] == "d1"


@pytest.mark.asyncio
async def test_save_scene_preserves_effect_state(db):
    """Re-saving a scene via save_scene should not delete its effect state."""
    await db.save_scene(
        {"id": "s1", "name": "Scene 1", "mapping_type": "linear", "effect_mode": "independent"}
    )
    await db.save_scene_effect_state("s1", "BeatPulse", '{"gamma": 2.0}')
    # Update the scene name — must not wipe effect state
    await db.save_scene(
        {"id": "s1", "name": "Renamed", "mapping_type": "linear", "effect_mode": "independent"}
    )
    state = await db.load_scene_effect_state("s1")
    assert state is not None
    assert state["effect_class"] == "BeatPulse"


@pytest.mark.asyncio
async def test_save_scene_preserves_placements(db):
    """Re-saving a scene via save_scene should not cascade-delete its placements."""
    await db.upsert_device({"id": "d1", "name": "Dev1", "backend": "lifx", "led_count": 10})
    await db.save_scene(
        {"id": "s1", "name": "Scene 1", "mapping_type": "linear", "effect_mode": "independent"}
    )
    await db.save_placement(
        {
            "scene_id": "s1",
            "device_id": "d1",
            "position_x": 1.0,
            "position_y": 0.0,
            "position_z": 0.0,
            "geometry_type": "strip",
        }
    )
    # Upsert the scene with new mapping_type — placements must survive
    await db.save_scene(
        {"id": "s1", "name": "Scene 1", "mapping_type": "radial", "effect_mode": "independent"}
    )
    placements = await db.load_scene_placements("s1")
    assert len(placements) == 1
    assert placements[0]["device_id"] == "d1"


# --- Multi-scene concurrent activation ---


@pytest.mark.asyncio
async def test_set_scene_active_concurrent_does_not_deactivate_other(db):
    """set_scene_active on one scene must not touch another already-active scene."""
    await db.save_scene(
        {"id": "s1", "name": "S1", "mapping_type": "linear", "effect_mode": "independent"}
    )
    await db.save_scene(
        {"id": "s2", "name": "S2", "mapping_type": "linear", "effect_mode": "independent"}
    )
    # Activate s1 first, then s2; both must remain active
    await db.set_scene_active("s1")
    await db.set_scene_active("s2")
    scenes = await db.load_scenes()
    by_id = {s["id"]: s for s in scenes}
    assert by_id["s1"]["is_active"] == 1, "s1 should still be active after s2 was activated"
    assert by_id["s2"]["is_active"] == 1


# --- set_scene_inactive only deactivates one scene ---


@pytest.mark.asyncio
async def test_set_scene_inactive_leaves_other_scenes_active(db):
    """set_scene_inactive on one scene must not deactivate other active scenes."""
    await db.save_scene(
        {"id": "s1", "name": "S1", "mapping_type": "linear", "effect_mode": "independent"}
    )
    await db.save_scene(
        {"id": "s2", "name": "S2", "mapping_type": "linear", "effect_mode": "independent"}
    )
    await db.save_scene(
        {"id": "s3", "name": "S3", "mapping_type": "linear", "effect_mode": "independent"}
    )
    await db.set_scene_active("s1")
    await db.set_scene_active("s2")
    await db.set_scene_active("s3")
    # Deactivate only s2
    await db.set_scene_inactive("s2")
    scenes = await db.load_scenes()
    by_id = {s["id"]: s for s in scenes}
    assert by_id["s1"]["is_active"] == 1, "s1 must remain active"
    assert by_id["s2"]["is_active"] == 0, "s2 must be inactive"
    assert by_id["s3"]["is_active"] == 1, "s3 must remain active"


# --- load_scene_by_id ---


@pytest.mark.asyncio
async def test_load_scene_by_id_returns_correct_scene(db):
    """load_scene_by_id returns the exact scene dict for a known ID."""
    await db.save_scene(
        {"id": "main", "name": "Main Stage", "mapping_type": "radial", "effect_mode": "spatial"}
    )
    await db.save_scene(
        {"id": "booth", "name": "DJ Booth", "mapping_type": "linear", "effect_mode": "independent"}
    )
    scene = await db.load_scene_by_id("main")
    assert scene is not None
    assert scene["id"] == "main"
    assert scene["name"] == "Main Stage"
    assert scene["mapping_type"] == "radial"


@pytest.mark.asyncio
async def test_load_scene_by_id_returns_none_for_missing(db):
    """load_scene_by_id returns None when the scene ID does not exist."""
    result = await db.load_scene_by_id("nonexistent-scene")
    assert result is None


# --- device_exists ---


@pytest.mark.asyncio
async def test_device_exists_returns_true_for_known_device(db):
    """device_exists returns True when the device has been upserted."""
    await db.upsert_device({"id": "lifx:aa", "name": "Strip", "backend": "lifx", "led_count": 30})
    assert await db.device_exists("lifx:aa") is True


@pytest.mark.asyncio
async def test_device_exists_returns_false_for_unknown_device(db):
    """device_exists returns False when no matching device exists."""
    assert await db.device_exists("govee:not-here") is False


@pytest.mark.asyncio
async def test_device_exists_false_after_delete(db):
    """device_exists returns False once a device has been deleted."""
    await db.upsert_device({"id": "lifx:aa", "name": "Strip", "backend": "lifx", "led_count": 30})
    await db.delete_device("lifx:aa")
    assert await db.device_exists("lifx:aa") is False


# --- Migration rollback on failure ---


@pytest.mark.asyncio
async def test_migration_rollback_on_bad_sql(tmp_path):
    """A migration with malformed SQL rolls back and leaves schema_version unchanged."""
    import shutil

    from dj_ledfx.persistence import state_db as state_db_module

    # Open a fresh DB to apply the real migrations (version 2)
    db_path = tmp_path / "state.db"
    good_db = StateDB(db_path)
    await good_db.open()
    version_before = await good_db.get_schema_version()
    await good_db.close()

    # Inject a fake migration directory containing a bad SQL file at version 999
    fake_migrations = tmp_path / "fake_migrations"
    fake_migrations.mkdir()
    # Copy existing valid migrations so the DB doesn't re-apply them
    real_migrations = Path(state_db_module.__file__).parent / "migrations"
    for f in real_migrations.glob("*.sql"):
        shutil.copy(f, fake_migrations / f.name)
    # Plant a bad migration that will cause a parse/execute error
    (fake_migrations / "999_bad.sql").write_text("THIS IS NOT VALID SQL !!!;")

    # Monkey-patch the migrations directory to point at our fake one
    original_dir = state_db_module._MIGRATIONS_DIR
    state_db_module._MIGRATIONS_DIR = fake_migrations
    try:
        bad_db = StateDB(db_path)
        with pytest.raises(sqlite3.OperationalError):
            await bad_db.open()
        # Verify schema version was NOT advanced to 999
        # Re-open with valid migrations to read the version
        state_db_module._MIGRATIONS_DIR = original_dir
        check_db = StateDB(db_path)
        await check_db.open()
        version_after = await check_db.get_schema_version()
        await check_db.close()
        assert version_after == version_before, (
            f"Schema version should remain {version_before}, got {version_after}"
        )
    finally:
        state_db_module._MIGRATIONS_DIR = original_dir


# --- close() is safe during concurrent operation ---


@pytest.mark.asyncio
async def test_close_safe_during_concurrent_read(tmp_path):
    """Calling close() while a read is in progress does not crash or deadlock."""
    db_path = tmp_path / "state.db"
    state_db = StateDB(db_path)
    await state_db.open()

    # Schedule a read and a close concurrently; both must complete without exception
    async def do_read() -> None:
        await state_db._execute_read("SELECT name FROM sqlite_master WHERE type='table'")

    async def do_close() -> None:
        await state_db.close()

    # Run both; order is non-deterministic but neither must raise
    results = await asyncio.gather(do_read(), do_close(), return_exceptions=True)
    for result in results:
        assert not isinstance(result, Exception), f"Unexpected exception: {result}"
