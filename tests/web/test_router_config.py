import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from dj_ledfx.config import AppConfig
from dj_ledfx.web.app import create_app


@pytest.fixture
def client(tmp_path):
    config = AppConfig()
    app = create_app(
        beat_clock=MagicMock(), effect_deck=MagicMock(),
        effect_engine=MagicMock(), device_manager=MagicMock(),
        scheduler=MagicMock(), preset_store=MagicMock(),
        scene_model=None, compositor=None,
        config=config, config_path=tmp_path / "config.toml",
    )
    return TestClient(app)


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
    toml_str = '[engine]\nfps = 120\n'
    resp = client.post("/api/config/import", content=toml_str)
    assert resp.status_code == 200
    assert resp.json()["engine"]["fps"] == 120
