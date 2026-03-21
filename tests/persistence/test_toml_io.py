"""Tests for TOML import/export marshaling."""

import json
from pathlib import Path

import pytest
import pytest_asyncio

from dj_ledfx.persistence.state_db import StateDB
from dj_ledfx.persistence.toml_io import export_toml, import_toml


@pytest_asyncio.fixture
async def db(tmp_path: Path):
    db_path = tmp_path / "state.db"
    state_db = StateDB(db_path)
    await state_db.open()
    yield state_db
    await state_db.close()


@pytest.mark.asyncio
async def test_export_empty_db(db):
    result = await export_toml(db)
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_export_round_trip_config(db):
    await db.save_config_key("engine", "fps", "120")
    await db.save_config_key("network", "interface", "192.168.1.1")
    toml_str = await export_toml(db)
    assert "fps" in toml_str
    assert "120" in toml_str
    assert "interface" in toml_str
    assert "192.168.1.1" in toml_str


@pytest.mark.asyncio
async def test_export_round_trip_devices(db):
    await db.upsert_device(
        {
            "id": "lifx:aabb",
            "name": "Kitchen Strip",
            "backend": "lifx",
            "led_count": 60,
            "ip": "192.168.1.42",
            "mac": "d073d5aabb",
            "last_latency_ms": 48.5,
        }
    )
    toml_str = await export_toml(db)
    assert "Kitchen Strip" in toml_str
    assert "lifx" in toml_str


@pytest.mark.asyncio
async def test_import_config(db):
    toml_str = """
[config.engine]
fps = 90

[config.network]
interface = "10.0.0.1"
"""
    await import_toml(db, toml_str)
    # load_all_config deserializes JSON-stored values back to Python types
    all_cfg = await db.load_all_config()
    assert all_cfg[("engine", "fps")] == 90
    assert all_cfg[("network", "interface")] == "10.0.0.1"


@pytest.mark.asyncio
async def test_import_devices(db):
    toml_str = """
[devices."Kitchen Strip"]
backend = "lifx"
led_count = 60
ip = "192.168.1.42"
mac = "d073d5aabb"
"""
    await import_toml(db, toml_str)
    devices = await db.load_devices()
    assert len(devices) == 1
    assert devices[0]["name"] == "Kitchen Strip"
    assert devices[0]["backend"] == "lifx"


@pytest.mark.asyncio
async def test_import_scenes(db):
    await db.upsert_device({"id": "lifx:aa", "name": "Strip", "backend": "lifx", "led_count": 60})

    toml_str = """
[scenes."dj-booth"]
name = "DJ Booth"
mapping_type = "linear"
effect_mode = "independent"
is_active = true

[scenes."dj-booth".effect]
effect_class = "beat_pulse"
params = { gamma = 3.0 }

[scenes."dj-booth".placements."Strip"]
position = [1.0, 2.0, 3.0]
geometry = "strip"
direction = [1.0, 0.0, 0.0]
length = 1.5
"""
    await import_toml(db, toml_str)
    scenes = await db.load_scenes()
    assert len(scenes) == 1
    assert scenes[0]["name"] == "DJ Booth"

    state = await db.load_scene_effect_state("dj-booth")
    assert state is not None
    params = json.loads(state["params"])
    assert params["gamma"] == 3.0

    placements = await db.load_scene_placements("dj-booth")
    assert len(placements) == 1
    assert placements[0]["position_x"] == 1.0


@pytest.mark.asyncio
async def test_import_presets(db):
    toml_str = """
[presets."My Preset"]
effect_class = "beat_pulse"
params = { gamma = 2.5 }
"""
    await import_toml(db, toml_str)
    presets = await db.load_presets()
    preset_by_name = {p["name"]: p for p in presets}
    assert "My Preset" in preset_by_name
    params = json.loads(preset_by_name["My Preset"]["params"])
    assert params["gamma"] == 2.5


@pytest.mark.asyncio
async def test_export_import_round_trip(db):
    """Full round-trip: populate DB, export to TOML, import into fresh DB."""
    await db.save_config_key("engine", "fps", "90")
    await db.upsert_device(
        {
            "id": "lifx:cc",
            "name": "Ceiling Strip",
            "backend": "lifx",
            "led_count": 82,
        }
    )
    await db.save_preset("My Wave", "rainbow_wave", json.dumps({"speed": 1.5}))

    toml_str = await export_toml(db)

    # Import into a fresh DB
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        db2 = StateDB(Path(tmpdir) / "state2.db")
        await db2.open()
        await import_toml(db2, toml_str)

        engine_cfg = await db2.load_config("engine")
        assert engine_cfg.get("fps") == "90"

        devices = await db2.load_devices()
        assert any(d["name"] == "Ceiling Strip" for d in devices)

        presets = await db2.load_presets()
        preset_names = {p["name"] for p in presets}
        assert "My Wave" in preset_names

        await db2.close()


@pytest.mark.asyncio
async def test_export_includes_mapping_params_and_effect_source(db):
    """Export includes mapping_params (JSON string) and effect_source when present.

    effect_source is a FK referencing scenes(id), so we create the source scene
    first, then a second scene that references it.
    """
    mapping_params = {"axis": "x", "scale": 2.0}

    # Source scene (must exist for FK constraint)
    await db.save_scene({"id": "source-scene", "name": "Source"})

    # Scene under test — references source-scene and has mapping_params
    await db.save_scene(
        {
            "id": "test-scene",
            "name": "Test Scene",
            "mapping_type": "linear",
            "mapping_params": json.dumps(mapping_params),
            "effect_source": "source-scene",
        }
    )

    toml_str = await export_toml(db)

    # Both fields must appear in the exported TOML
    assert "mapping_params" in toml_str
    assert "effect_source" in toml_str
    assert "source-scene" in toml_str
    # mapping_params values should be inlined (not double-encoded)
    assert "axis" in toml_str
    assert "scale" in toml_str


@pytest.mark.asyncio
async def test_import_preserves_boolean_type_fidelity(db):
    """import_toml stores booleans via json.dumps; load_all_config returns Python bool."""
    toml_str = """
[config.engine]
enabled = true
count = 42
ratio = 1.5
label = "hello"
"""
    await import_toml(db, toml_str)

    all_cfg = await db.load_all_config()

    # Boolean must come back as Python True, not the string "True"
    assert all_cfg[("engine", "enabled")] is True
    assert not isinstance(all_cfg[("engine", "enabled")], str)

    # Other types must also round-trip correctly
    assert all_cfg[("engine", "count")] == 42
    assert isinstance(all_cfg[("engine", "count")], int)
    assert all_cfg[("engine", "ratio")] == 1.5
    assert all_cfg[("engine", "label")] == "hello"


@pytest.mark.asyncio
async def test_import_mapping_params_and_effect_source_round_trip(db):
    """Import a TOML with scene mapping_params and effect_source; verify DB storage.

    effect_source is a scenes(id) FK, so a source scene must be imported first.
    We export both scenes from a single TOML where the source scene is defined
    before the referencing scene.
    """
    toml_str = """
[scenes."source"]
name = "Source"
mapping_type = "linear"

[scenes."stage"]
name = "Stage"
mapping_type = "radial"
effect_source = "source"

[scenes."stage".mapping_params]
radius = 3.0
center = [0.0, 0.0, 0.0]
"""
    await import_toml(db, toml_str)

    scenes = await db.load_scenes()
    scene_by_id = {s["id"]: s for s in scenes}
    assert "stage" in scene_by_id

    stage = scene_by_id["stage"]
    assert stage["effect_source"] == "source"
    assert stage["mapping_params"] is not None

    # mapping_params must be stored as a JSON string and parse back correctly
    params = json.loads(stage["mapping_params"])
    assert params["radius"] == 3.0
    assert params["center"] == [0.0, 0.0, 0.0]


@pytest.mark.asyncio
async def test_migrate_nested_device_config(tmp_path: Path):
    """_migrate_config_toml handles dotted sub-sections like [devices.lifx]."""
    from dj_ledfx.persistence.toml_io import migrate_from_toml

    config_toml = tmp_path / "config.toml"
    config_toml.write_text(
        """
[devices.lifx]
max_fps = 30
discovery_timeout = 5

[devices.govee]
segment_count = 15
"""
    )

    db_path = tmp_path / "state.db"
    state_db = StateDB(db_path)
    await state_db.open()

    await migrate_from_toml(state_db, config_path=config_toml)

    all_cfg = await state_db.load_all_config()

    # Dotted section "devices.lifx" must be stored as-is
    assert ("devices.lifx", "max_fps") in all_cfg
    assert all_cfg[("devices.lifx", "max_fps")] == 30
    assert ("devices.lifx", "discovery_timeout") in all_cfg
    assert all_cfg[("devices.lifx", "discovery_timeout")] == 5

    assert ("devices.govee", "segment_count") in all_cfg
    assert all_cfg[("devices.govee", "segment_count")] == 15

    # config.toml should have been renamed to .bak
    assert not config_toml.exists()
    assert (tmp_path / "config.toml.bak").exists()

    await state_db.close()
