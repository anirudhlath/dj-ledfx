from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.manager import DeviceManager
from dj_ledfx.events import EventBus
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.types import DeviceInfo
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


@pytest.fixture
def client_with_device():
    """Client with one real device registered."""
    manager = DeviceManager(EventBus())
    info = DeviceInfo(
        name="Strip1",
        device_type="lifx_strip",
        led_count=60,
        address="192.168.1.100",
        stable_id="lifx:strip1",
    )
    tracker = LatencyTracker(StaticLatency(50.0))

    adapter = MagicMock(spec=DeviceAdapter)
    adapter.device_info = info
    adapter.led_count = 60
    adapter.is_connected = True

    manager.add_device(adapter, tracker)

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
    return TestClient(app), manager


def test_list_devices_empty(client):
    resp = client.get("/api/devices")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_devices_includes_status(client_with_device):
    test_client, _ = client_with_device
    resp = test_client.get("/api/devices")
    assert resp.status_code == 200
    devices = resp.json()
    assert len(devices) == 1
    assert "status" in devices[0]
    assert devices[0]["status"] == "online"


def test_groups_crud(client):
    resp = client.post("/api/devices/groups", json={"name": "Booth", "color": "#00e5ff"})
    assert resp.status_code == 200
    resp = client.get("/api/devices/groups")
    assert "Booth" in resp.json()
    resp = client.delete("/api/devices/groups/Booth")
    assert resp.status_code == 200


def test_scan_endpoint_fallback():
    """POST /devices/scan with no orchestrator falls back to legacy rediscover."""
    manager = DeviceManager(EventBus())
    scheduler = MagicMock()
    scheduler.get_device_stats.return_value = []
    # Mock manager.rediscover to avoid real network calls
    manager.rediscover = AsyncMock(return_value=[])
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
    test_client = TestClient(app)
    resp = test_client.post("/api/devices/scan")
    assert resp.status_code == 200
    data = resp.json()
    assert "discovered" in data


def test_scan_endpoint_with_orchestrator():
    """POST /devices/scan uses DiscoveryOrchestrator when available."""
    manager = DeviceManager(EventBus())
    scheduler = MagicMock()
    scheduler.get_device_stats.return_value = []

    mock_orchestrator = MagicMock()
    mock_orchestrator.run_discovery = AsyncMock(return_value=2)

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
    app.state.discovery_orchestrator = mock_orchestrator

    test_client = TestClient(app)
    resp = test_client.post("/api/devices/scan")
    assert resp.status_code == 200
    assert resp.json()["discovered"] == 2
    mock_orchestrator.run_discovery.assert_called_once_with(waves=1)


def test_delete_device(client_with_device):
    test_client, manager = client_with_device
    resp = test_client.delete("/api/devices/Strip1")
    assert resp.status_code == 200
    assert resp.json()["status"] == "removed"
    assert manager.get_device("Strip1") is None


def test_delete_device_not_found(client):
    resp = client.delete("/api/devices/NonExistent")
    assert resp.status_code == 404
