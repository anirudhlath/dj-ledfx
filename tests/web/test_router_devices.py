import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.manager import DeviceManager
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.persistence.state_db import StateDB
from dj_ledfx.types import DeviceInfo
from dj_ledfx.web.app import create_app
from tests.web.conftest import mock_deps


@pytest.fixture
def client():
    manager = DeviceManager()
    scheduler = MagicMock()
    scheduler.get_device_stats.return_value = []
    app = create_app(**mock_deps(device_manager=manager, scheduler=scheduler))
    return TestClient(app)


@pytest.fixture
def client_with_device():
    """Client with one real device registered."""
    manager = DeviceManager()
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
    app = create_app(**mock_deps(device_manager=manager, scheduler=scheduler))
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
    assert devices[0]["id"] == "lifx:strip1"  # frames and stats are keyed by it


def test_groups_crud(client):
    resp = client.post("/api/devices/groups", json={"name": "Booth", "color": "#00e5ff"})
    assert resp.status_code == 200
    resp = client.get("/api/devices/groups")
    assert "Booth" in resp.json()
    resp = client.delete("/api/devices/groups/Booth")
    assert resp.status_code == 200


def _light(name: str, stable_id: str) -> MagicMock:
    adapter = MagicMock(spec=DeviceAdapter)
    adapter.device_info = DeviceInfo(
        name=name, device_type="lifx_bulb", led_count=1, address="127.0.0.1", stable_id=stable_id
    )
    adapter.led_count = 1
    adapter.is_connected = True
    return adapter


def test_the_old_discover_runs_a_scan_and_names_what_it_brought_online():
    """POST /devices/discover, the old UI's: the orchestrator's scan, in the old UI's shape."""
    manager = DeviceManager()
    tracker = LatencyTracker(StaticLatency(50.0))
    manager.add_device(_light("Strip1", "lifx:strip1"), tracker)  # online already
    manager.add_device_from_info(
        _light("Bulb", "lifx:bulb").device_info, tracker=tracker, status="offline"
    )

    async def scan() -> int:
        manager.promote_device("lifx:bulb", _light("Bulb", "lifx:bulb"))  # back
        manager.add_device(_light("Lamp", "lifx:lamp"), tracker)  # new
        return 2

    orchestrator = MagicMock(run_scan=AsyncMock(side_effect=scan))
    scheduler = MagicMock(get_device_stats=MagicMock(return_value=[]))
    app = create_app(
        **mock_deps(
            device_manager=manager, scheduler=scheduler, discovery_orchestrator=orchestrator
        )
    )

    resp = TestClient(app).post("/api/devices/discover")

    assert resp.status_code == 200
    assert resp.json() == {"discovered": ["Bulb", "Lamp"]}
    orchestrator.run_scan.assert_awaited_once()


@pytest.mark.parametrize("path", ["/api/devices/scan", "/api/devices/discover"])
def test_a_scan_needs_the_orchestrator(client, path):
    assert client.post(path).status_code == 503


def test_scan_endpoint_with_orchestrator():
    """POST /devices/scan uses DiscoveryOrchestrator when available."""
    manager = DeviceManager()
    scheduler = MagicMock()
    scheduler.get_device_stats.return_value = []

    mock_orchestrator = MagicMock()
    mock_orchestrator.run_scan = AsyncMock(return_value=2)

    app = create_app(
        **mock_deps(
            device_manager=manager, scheduler=scheduler, discovery_orchestrator=mock_orchestrator
        )
    )

    test_client = TestClient(app)
    resp = test_client.post("/api/devices/scan")
    assert resp.status_code == 200
    assert resp.json()["discovered"] == 2
    mock_orchestrator.run_scan.assert_called_once()


def test_delete_device(client_with_device):
    test_client, manager = client_with_device
    resp = test_client.delete("/api/devices/Strip1")
    assert resp.status_code == 200
    assert resp.json()["status"] == "removed"
    assert manager.get_device("Strip1") is None


def test_delete_device_not_found(client):
    resp = client.delete("/api/devices/NonExistent")
    assert resp.status_code == 404


def test_delete_device_persists_to_db(tmp_path):
    """DELETE /devices/{name} removes the device from both the manager and the DB."""
    db = StateDB(tmp_path / "state.db")
    asyncio.run(db.open())

    manager = DeviceManager()
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

    # Pre-seed the device in the DB so there is a row to delete
    asyncio.run(db.upsert_device({"id": "lifx:strip1", "name": "Strip1", "backend": "lifx"}))

    scheduler = MagicMock()
    scheduler.get_device_stats.return_value = []
    app = create_app(**mock_deps(device_manager=manager, scheduler=scheduler, state_db=db))
    test_client = TestClient(app)

    try:
        resp = test_client.delete("/api/devices/Strip1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "removed"

        # Device gone from manager
        assert manager.get_device("Strip1") is None

        # Device gone from DB
        devices_in_db = asyncio.run(db.load_devices())
        ids_in_db = [d["id"] for d in devices_in_db]
        assert "lifx:strip1" not in ids_in_db
    finally:
        asyncio.run(db.close())
