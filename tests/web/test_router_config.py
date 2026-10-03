import asyncio

import pytest
import tomli_w
from fastapi.testclient import TestClient

from dj_ledfx.config import AppConfig, load_config
from dj_ledfx.persistence.state_db import StateDB
from dj_ledfx.web.app import create_app
from tests.web.conftest import mock_deps


@pytest.fixture
def client(tmp_path):
    config = AppConfig()
    app = create_app(**mock_deps(config=config, config_path=tmp_path / "config.toml"))
    return TestClient(app)


@pytest.fixture
def client_with_db(tmp_path):
    config = AppConfig()
    db = StateDB(tmp_path / "state.db")
    asyncio.run(db.open())
    app = create_app(**mock_deps(config=config, state_db=db))
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


# Keys a deployed config.toml and state.db carry that nothing reads (rulings A5 and C2).
# Each section is built from its dataclass, which refuses a key it doesn't have, so the
# fields stay until every way in ignores keys it doesn't know.
UNREAD = {
    "discovery": {"unicast_concurrency": 50, "unicast_timeout_s": 0.5, "subnet_mask": 24},
    "devices": {"govee": {"probe_interval_s": 5.0}},
}


def test_a_config_that_carries_unread_keys_still_loads(client, tmp_path):
    old_backup = tomli_w.dumps(UNREAD)
    assert client.post("/api/config/import", content=old_backup).status_code == 200
    assert client.put("/api/config", json=UNREAD).status_code == 200
    config_toml = tmp_path / "old.toml"
    config_toml.write_text(old_backup)
    assert load_config(config_toml).discovery.subnet_mask == 24


def test_state_export_no_db(client):
    resp = client.get("/api/state/export")
    assert resp.status_code == 503


def test_state_import_no_db(client):
    resp = client.post("/api/state/import", content="[presets]\n")
    assert resp.status_code == 503


def test_state_export_with_db(client_with_db):
    resp = client_with_db.get("/api/state/export")
    assert resp.status_code == 200
