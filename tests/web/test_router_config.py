import asyncio
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from dj_ledfx.config import AppConfig
from dj_ledfx.persistence.state_db import StateDB
from dj_ledfx.web.app import create_app


@pytest.fixture
def client(tmp_path):
    config = AppConfig()
    app = create_app(
        beat_clock=MagicMock(),
        effect_deck=MagicMock(),
        effect_engine=MagicMock(),
        device_manager=MagicMock(),
        scheduler=MagicMock(),
        preset_store=MagicMock(),
        scene_model=None,
        compositor=None,
        config=config,
        config_path=tmp_path / "config.toml",
    )
    return TestClient(app)


@pytest.fixture
def client_with_db(tmp_path):
    config = AppConfig()
    db = StateDB(tmp_path / "state.db")
    asyncio.run(db.open())
    app = create_app(
        beat_clock=MagicMock(),
        effect_deck=MagicMock(),
        effect_engine=MagicMock(),
        device_manager=MagicMock(),
        scheduler=MagicMock(),
        preset_store=MagicMock(),
        scene_model=None,
        compositor=None,
        config=config,
        config_path=None,
        state_db=db,
    )
    yield TestClient(app)
    asyncio.run(db.close())


def test_get_config(client):
    resp = client.get("/api/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["engine"]["fps"] == 60


def test_update_config(client):
    resp = client.put("/api/config", json={"engine": {"fps": 90}})
    assert resp.status_code == 200
    assert resp.json()["engine"]["fps"] == 90


def test_export_config(client):
    resp = client.get("/api/config/export")
    assert resp.status_code == 200
    assert "fps" in resp.text


def test_import_config(client):
    toml_str = "[engine]\nfps = 120\n"
    resp = client.post("/api/config/import", content=toml_str)
    assert resp.status_code == 200
    assert resp.json()["engine"]["fps"] == 120


def test_state_export_no_db(client):
    resp = client.get("/api/state/export")
    assert resp.status_code == 503


def test_state_import_no_db(client):
    resp = client.post("/api/state/import", content="[presets]\n")
    assert resp.status_code == 503


def test_state_export_with_db(client_with_db):
    resp = client_with_db.get("/api/state/export")
    assert resp.status_code == 200


def test_state_import_with_db(client_with_db):
    toml_str = '[presets."My Preset"]\neffect_class = "beat_pulse"\n\n[presets."My Preset".params]\n'
    resp = client_with_db.post("/api/state/import", content=toml_str)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
