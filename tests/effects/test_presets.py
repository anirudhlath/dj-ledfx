import pytest

from dj_ledfx.effects.presets import Preset, PresetStore


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
