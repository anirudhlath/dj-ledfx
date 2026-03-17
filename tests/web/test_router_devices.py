from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from dj_ledfx.devices.manager import DeviceManager
from dj_ledfx.events import EventBus
from dj_ledfx.web.app import create_app


@pytest.fixture
def client():
    manager = DeviceManager(EventBus())
    scheduler = MagicMock()
    scheduler.get_device_stats.return_value = []
    app = create_app(
        beat_clock=MagicMock(),
        effect_deck=MagicMock(),
        effect_engine=MagicMock(),
        device_manager=manager,
        scheduler=scheduler,
        preset_store=MagicMock(),
        scene_model=None,
        compositor=None,
        config=MagicMock(web=MagicMock(cors_origins=["*"])),
        config_path=None,
    )
    return TestClient(app)


def test_list_devices_empty(client):
    resp = client.get("/api/devices")
    assert resp.status_code == 200
    assert resp.json() == []


def test_groups_crud(client):
    resp = client.post("/api/devices/groups", json={"name": "Booth", "color": "#00e5ff"})
    assert resp.status_code == 200
    resp = client.get("/api/devices/groups")
    assert "Booth" in resp.json()
    resp = client.delete("/api/devices/groups/Booth")
    assert resp.status_code == 200
