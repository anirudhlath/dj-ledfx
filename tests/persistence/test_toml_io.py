"""Tests for TOML import/export marshaling."""

import errno
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from map_home import tiny_home

from dj_ledfx.home.shapes import CylinderShape, GridShape, Placement, PointShape
from dj_ledfx.home.store import HomeStore
from dj_ledfx.persistence.state_db import StateDB
from dj_ledfx.persistence.toml_io import export_toml, import_toml, migrate_from_toml
from dj_ledfx.zones.model import Assignment, StoppedLook, ZoneRecord
from dj_ledfx.zones.store import ZoneStore


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


STARTED = datetime(2026, 9, 24, 19, 30, 15, 250000, tzinfo=UTC)
INSERT_LOOK = "INSERT INTO looks (id, body, created_at, updated_at) VALUES (?, ?, ?, ?)"
LOOK_ROW = ("mine-0badc0de", '{"name": "Mine", "derivedFrom": null}', "2026-09-24T18:00", "t2")


async def _zones_looks_and_running(db: StateDB) -> None:
    store = ZoneStore(db)
    await store.save_zone(ZoneRecord(id="desk", name="Office desk", lights=("lifx:b", "lifx:a")))
    await store.save_zone(ZoneRecord(id="all-lights", name="All lights", all_lights=True))
    await db.write(INSERT_LOOK, LOOK_ROW)
    await db.write("INSERT INTO look_stars (look_id) VALUES (?)", ("classic-breathe",))
    await store.save_assignment(
        Assignment("desk", "mine-0badc0de", LOOK_ROW[1], 0.5, ("lifx:b",), STARTED)
    )


@pytest.mark.asyncio
async def test_zones_looks_stars_and_running_round_trip(db, tmp_path: Path) -> None:
    await _zones_looks_and_running(db)
    text = await export_toml(db)

    fresh = StateDB(tmp_path / "fresh.db")
    await fresh.open()
    try:
        await import_toml(fresh, text)

        assert await ZoneStore(fresh).load_zones() == await ZoneStore(db).load_zones()
        assert await ZoneStore(fresh).load_assignments() == await ZoneStore(db).load_assignments()
        looks = await fresh.fetch_all("SELECT id, body, created_at, updated_at FROM looks")
        assert looks == [LOOK_ROW]
        assert await fresh.fetch_all("SELECT look_id FROM look_stars") == [("classic-breathe",)]
    finally:
        await fresh.close()


@pytest.mark.asyncio
async def test_import_skips_what_it_cannot_use(db) -> None:
    text = """
[zones.desk]
name = "Desk"
kind = "castle"
lights = ["lifx:a"]

[looks.firmware]
body = "{}"

[looks.mine-nobody]
created_at = "2026-09-24T18:00"

[running.desk]
look_id = "classic-breathe"
look = "{}"
brightness = 0.5
lights = ["lifx:a"]
started_at = "not a time"

[running.nowhere]
look_id = "classic-breathe"
look = "{}"
brightness = 1.0
lights = []
started_at = 2026-09-24T19:00:00Z
"""
    await import_toml(db, text)

    assert await ZoneStore(db).load_zones() == [
        ZoneRecord(id="desk", name="Desk", kind="group", lights=("lifx:a",))
    ]
    assert await db.fetch_all("SELECT id FROM looks") == []
    assert await ZoneStore(db).load_assignments() == []


@pytest.mark.asyncio
async def test_migration_keeps_value_types(tmp_path: Path) -> None:
    config_toml = tmp_path / "config.toml"
    config_toml.write_text(
        '[network]\ninterface = "auto"\npassive_mode = false\n\n'
        '[web]\ncors_origins = ["http://localhost:5173"]\n'
    )
    db = StateDB(tmp_path / "state.db")
    await db.open()
    try:
        await migrate_from_toml(db, config_path=config_toml)
        config = await db.load_all_config()
    finally:
        await db.close()

    assert config[("network", "interface")] == "auto"
    assert config[("network", "passive_mode")] is False
    assert config[("web", "cors_origins")] == ["http://localhost:5173"]


@pytest.mark.asyncio
async def test_migration_leaves_a_file_it_cannot_rename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bind-mounted config.toml can't be renamed; the migration still counts."""
    config_toml = tmp_path / "config.toml"
    config_toml.write_text("[engine]\nfps = 90\n")

    def busy(self: Path, target: object) -> Path:
        raise OSError(errno.EBUSY, "Device or resource busy")

    monkeypatch.setattr(Path, "rename", busy)
    db = StateDB(tmp_path / "state.db")
    await db.open()
    try:
        await migrate_from_toml(db, config_path=config_toml)
        config = await db.load_all_config()
    finally:
        await db.close()

    assert config[("engine", "fps")] == 90
    assert config_toml.exists()


@pytest.mark.asyncio
async def test_the_map_and_the_placements_round_trip(db, tmp_path: Path) -> None:
    store = HomeStore(db)
    await store.save_home(tiny_home(ceiling=2.6))
    confirmed = Placement(
        PointShape((1.0, 3.5, 1.0)), "", True, datetime(2026, 9, 24, 19, 0, tzinfo=UTC)
    )
    await store.save_placement("lamp", confirmed)
    part = Placement(GridShape((6.0, 3.0, 1.0), 0.4, 0.2, (0.0, 90.0, 0.0)), "columns")
    await store.save_placement("openrgb:localhost:6742:1", part)
    text = await export_toml(db)

    fresh = StateDB(tmp_path / "fresh.db")
    await fresh.open()
    try:
        await import_toml(fresh, text)

        assert await HomeStore(fresh).load_home() == tiny_home(ceiling=2.6)
        assert await HomeStore(fresh).load_placements() == {
            "lamp": confirmed,
            "openrgb:localhost:6742:1": part,
        }
    finally:
        await fresh.close()


@pytest.mark.asyncio
async def test_import_skips_a_bad_map_and_bad_placements(db) -> None:
    text = """
[home]
body = '{"rooms": []}'

[placements.lamp]
shape = { kind = "point", position = [1.0, 2.0] }

[placements.rope]
shape = { kind = "line", path = [[0.0, 0.0, 1.0], [2.0, 0.0, 1.0]] }
led_order = "rows"

[placements.bulb]
shape = "a point"

[placements.tube]
confirmed = true
shape = { kind = "cylinder", base = [1.0, 1.0, 0.0], height = 0.5, radius = 0.05 }
"""
    await import_toml(db, text)

    assert await db.fetch_all("SELECT body FROM home_map") == []  # the map wasn't touched
    placements = await HomeStore(db).load_placements()
    assert placements == {
        "tube": Placement(CylinderShape((1.0, 1.0, 0.0), 0.5, 0.05), "bottom-to-top", True)
    }


@pytest.mark.asyncio
async def test_start_again_round_trips_and_keeps_the_newer_stop(db, tmp_path: Path) -> None:
    at = datetime(2026, 9, 24, 19, 0, tzinfo=UTC)
    shelf = StoppedLook("shelf", "classic-strobe", at, at + timedelta(minutes=9))
    await ZoneStore(db).remember(
        [StoppedLook("desk", "classic-breathe", at, at + timedelta(minutes=5)), shelf]
    )
    text = await export_toml(db)
    assert "[[recent]]" in text

    fresh = StateDB(tmp_path / "fresh.db")
    await fresh.open()
    try:
        desk_here = StoppedLook("desk", "classic-breathe", at, at + timedelta(minutes=20))
        shelf_here = StoppedLook("shelf", "classic-strobe", at, at + timedelta(minutes=1))
        await ZoneStore(fresh).remember([desk_here, shelf_here])

        await import_toml(fresh, text)

        assert await ZoneStore(fresh).load_recent() == [desk_here, shelf]
    finally:
        await fresh.close()


@pytest.mark.asyncio
async def test_import_skips_start_again_entries_it_cannot_use(db) -> None:
    text = """
[[recent]]
zone_id = "desk"
look_id = "classic-breathe"
started_at = 2026-09-24T19:00:00Z
stopped_at = 2026-09-24T19:05:00Z

[[recent]]
zone_id = "shelf"
look_id = "classic-strobe"
started_at = "not a time"
stopped_at = 2026-09-24T19:05:00Z

[[recent]]
look_id = "classic-strobe"
started_at = 2026-09-24T19:00:00Z
stopped_at = 2026-09-24T19:05:00Z
"""
    await import_toml(db, text)

    at = datetime(2026, 9, 24, 19, 0, tzinfo=UTC)
    assert await ZoneStore(db).load_recent() == [
        StoppedLook("desk", "classic-breathe", at, at + timedelta(minutes=5))
    ]
