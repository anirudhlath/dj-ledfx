from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from dj_ledfx.effects.beat_pulse import BeatPulse
from dj_ledfx.effects.deck import EffectDeck
from dj_ledfx.effects.presets import PresetStore
from dj_ledfx.web.app import create_app


@pytest.fixture
def client(tmp_path):
    deck = EffectDeck(BeatPulse())
    store = PresetStore(tmp_path / "presets.toml")
    app = create_app(
        beat_clock=MagicMock(),
        effect_deck=deck,
        effect_engine=MagicMock(),
        device_manager=MagicMock(),
        scheduler=MagicMock(),
        preset_store=store,
        scene_model=None,
        compositor=None,
        config=MagicMock(web=MagicMock(cors_origins=["*"])),
        config_path=None,
    )
    return TestClient(app)


def test_list_effects(client):
    resp = client.get("/api/effects")
    assert resp.status_code == 200
    data = resp.json()
    assert "beat_pulse" in data


def test_get_active_effect(client):
    resp = client.get("/api/effects/active")
    assert resp.status_code == 200
    assert resp.json()["effect"] == "beat_pulse"


def test_update_params(client):
    resp = client.put("/api/effects/active", json={"params": {"gamma": 3.0}})
    assert resp.status_code == 200
    resp2 = client.get("/api/effects/active")
    assert resp2.json()["params"]["gamma"] == 3.0


def test_presets_crud(client):
    resp = client.post("/api/presets", json={"name": "Test"})
    assert resp.status_code == 200
    resp = client.get("/api/presets")
    assert len(resp.json()) == 1
    resp = client.post("/api/presets/Test/load")
    assert resp.status_code == 200
    resp = client.delete("/api/presets/Test")
    assert resp.status_code == 200
    assert len(client.get("/api/presets").json()) == 0


def test_preset_update(client):
    client.post("/api/presets", json={"name": "Test"})
    resp = client.put("/api/presets/Test", json={"params": {"gamma": 4.0}})
    assert resp.status_code == 200
