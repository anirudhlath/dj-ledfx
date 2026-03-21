import pytest
import pytest_asyncio

from dj_ledfx.effects.presets import Preset, PresetStore
from dj_ledfx.persistence.state_db import StateDB


@pytest_asyncio.fixture
async def db_store(tmp_path):
    db = StateDB(tmp_path / "state.db")
    await db.open()
    store = PresetStore(state_db=db)
    await store.load_from_db()
    yield store
    await db.close()


@pytest.mark.asyncio
async def test_db_store_save_and_list(db_store):
    await db_store.save_async(Preset("P1", "beat_pulse", {"gamma": 2.5}))
    presets = db_store.list()
    assert len(presets) == 1
    assert presets[0].name == "P1"


@pytest.mark.asyncio
async def test_db_store_delete(db_store):
    await db_store.save_async(Preset("P1", "beat_pulse", {}))
    await db_store.delete_async("P1")
    assert len(db_store.list()) == 0


@pytest.mark.asyncio
async def test_db_store_persistence(tmp_path):
    db = StateDB(tmp_path / "state.db")
    await db.open()
    store = PresetStore(state_db=db)
    await store.load_from_db()
    await store.save_async(Preset("P1", "beat_pulse", {"gamma": 3.0}))
    await db.close()

    db2 = StateDB(tmp_path / "state.db")
    await db2.open()
    store2 = PresetStore(state_db=db2)
    await store2.load_from_db()
    presets = store2.list()
    assert len(presets) == 1
    assert presets[0].params["gamma"] == 3.0
    await db2.close()


def test_preset_save_and_list(tmp_path):
    store = PresetStore(tmp_path / "presets.toml")
    store.save(Preset(name="Cool Pulse", effect_class="beat_pulse", params={"gamma": 3.0}))
    presets = store.list()
    assert len(presets) == 1
    assert presets[0].name == "Cool Pulse"
    assert presets[0].params["gamma"] == 3.0


def test_preset_load(tmp_path):
    store = PresetStore(tmp_path / "presets.toml")
    store.save(Preset(name="A", effect_class="beat_pulse", params={"gamma": 2.0}))
    preset = store.load("A")
    assert preset.effect_class == "beat_pulse"


def test_preset_delete(tmp_path):
    store = PresetStore(tmp_path / "presets.toml")
    store.save(Preset(name="A", effect_class="beat_pulse", params={}))
    store.delete("A")
    assert len(store.list()) == 0


def test_preset_load_nonexistent(tmp_path):
    store = PresetStore(tmp_path / "presets.toml")
    with pytest.raises(KeyError):
        store.load("nope")


def test_preset_persistence(tmp_path):
    path = tmp_path / "presets.toml"
    PresetStore(path).save(Preset(name="X", effect_class="beat_pulse", params={"gamma": 1.5}))
    store2 = PresetStore(path)
    assert store2.load("X").params["gamma"] == 1.5
