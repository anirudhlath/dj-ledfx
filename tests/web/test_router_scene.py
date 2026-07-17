from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from dj_ledfx.persistence.state_db import StateDB
from dj_ledfx.spatial.compositor import SpatialCompositor
from dj_ledfx.spatial.geometry import PointGeometry, StripGeometry
from dj_ledfx.spatial.mapping import LinearMapping
from dj_ledfx.spatial.scene import DevicePlacement, SceneModel
from dj_ledfx.web.app import create_app


def _make_test_app(
    scene: SceneModel | None = None,
    state_db: StateDB | None = None,
    pipeline_manager: object | None = None,
) -> TestClient:
    """Create a test FastAPI app with a scene model."""
    compositor = None
    if scene and scene.placements:
        compositor = SpatialCompositor(scene, LinearMapping())

    mock_config = MagicMock()
    mock_config.web.cors_origins = ["*"]
    mock_config.web.static_dir = None
    mock_config.scene_config = None

    mock_device_manager = MagicMock()
    mock_device_manager.get_device.return_value = None
    mock_device_manager.resolve_stable_id.side_effect = lambda name: name

    app = create_app(
        beat_clock=MagicMock(),
        effect_deck=MagicMock(),
        effect_engine=MagicMock(),
        device_manager=mock_device_manager,
        scheduler=MagicMock(),
        preset_store=MagicMock(),
        scene_model=scene,
        compositor=compositor,
        config=mock_config,
        config_path=None,
        state_db=state_db,
        pipeline_manager=pipeline_manager,
    )
    return TestClient(app)


def _make_db_client(tmp_path, pm=None):
    """Return (client, db, pm) with a real StateDB and a configurable pipeline_manager.

    If pm is None, a MagicMock is created with standard async methods configured.
    Closing the db is the caller's responsibility.
    """
    db = StateDB(tmp_path / "state.db")
    asyncio.run(db.open())
    if pm is None:
        pm = MagicMock()
        pm.activate_scene = AsyncMock()
        pm.deactivate_scene = AsyncMock()
        pm.is_scene_active.return_value = False
        pm.set_scene_effect.return_value = {}
    client = _make_test_app(state_db=db, pipeline_manager=pm)
    return client, db, pm


def _make_real_device_client(
    tmp_path,
    *,
    name: str = "My Strip",
    stable_id: str = "lifx:my_strip",
    led_count: int = 30,
):
    """Return (client, db) with a real DeviceManager containing one named device.

    Closing the db is the caller's responsibility.
    """
    from dj_ledfx.devices.adapter import DeviceAdapter
    from dj_ledfx.devices.manager import DeviceManager
    from dj_ledfx.events import EventBus
    from dj_ledfx.latency.strategies import StaticLatency
    from dj_ledfx.latency.tracker import LatencyTracker
    from dj_ledfx.types import DeviceInfo

    db = StateDB(tmp_path / "state.db")
    asyncio.run(db.open())

    manager = DeviceManager(EventBus())
    info = DeviceInfo(
        name=name,
        device_type="lifx_strip",
        led_count=led_count,
        address="192.168.1.50",
        stable_id=stable_id,
    )
    tracker = LatencyTracker(StaticLatency(50.0))
    adapter = MagicMock(spec=DeviceAdapter)
    adapter.device_info = info
    adapter.led_count = led_count
    adapter.is_connected = True
    manager.add_device(adapter, tracker)

    mock_config = MagicMock()
    mock_config.web.cors_origins = ["*"]
    mock_config.web.static_dir = None
    mock_config.scene_config = None

    from dj_ledfx.web.app import create_app as _create_app

    app = _create_app(
        beat_clock=MagicMock(),
        effect_deck=MagicMock(),
        effect_engine=MagicMock(),
        device_manager=manager,
        scheduler=MagicMock(),
        preset_store=MagicMock(),
        scene_model=None,
        compositor=None,
        config=mock_config,
        config_path=None,
        state_db=db,
    )
    client = TestClient(app)
    return client, db


class TestSceneEndpoints:
    def test_get_scene_empty(self) -> None:
        client = _make_test_app(SceneModel(placements={}))
        resp = client.get("/api/scene")
        assert resp.status_code == 200
        data = resp.json()
        assert data["placements"] == []

    def test_get_scene_with_placements(self) -> None:
        scene = SceneModel(
            placements={
                "lamp": DevicePlacement("lamp", (1.0, 2.0, 0.0), PointGeometry(), 1),
            }
        )
        client = _make_test_app(scene)
        resp = client.get("/api/scene")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["placements"]) == 1
        assert data["placements"][0]["device_id"] == "lamp"
        assert data["placements"][0]["position"] == [1.0, 2.0, 0.0]

    def test_get_scene_devices(self) -> None:
        scene = SceneModel(
            placements={
                "lamp": DevicePlacement("lamp", (1.0, 2.0, 0.0), PointGeometry(), 1),
                "strip": DevicePlacement(
                    "strip",
                    (0.0, 0.0, 0.0),
                    StripGeometry(direction=(1.0, 0.0, 0.0), length=1.0),
                    10,
                ),
            }
        )
        client = _make_test_app(scene)
        resp = client.get("/api/scene/devices")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_put_scene_device_update_position(self) -> None:
        scene = SceneModel(
            placements={
                "lamp": DevicePlacement("lamp", (0.0, 0.0, 0.0), PointGeometry(), 1),
            }
        )
        client = _make_test_app(scene)
        resp = client.put("/api/scene/devices/lamp", json={"position": [5.0, 3.0, 1.0]})
        assert resp.status_code == 200
        assert resp.json()["position"] == [5.0, 3.0, 1.0]
        assert scene.placements["lamp"].position == (5.0, 3.0, 1.0)

    def test_delete_scene_device(self) -> None:
        scene = SceneModel(
            placements={
                "lamp": DevicePlacement("lamp", (0.0, 0.0, 0.0), PointGeometry(), 1),
            }
        )
        client = _make_test_app(scene)
        resp = client.delete("/api/scene/devices/lamp")
        assert resp.status_code == 200
        assert "lamp" not in scene.placements

    def test_delete_scene_device_not_found(self) -> None:
        scene = SceneModel(placements={})
        client = _make_test_app(scene)
        resp = client.delete("/api/scene/devices/nonexistent")
        assert resp.status_code == 404

    def test_put_scene_device_add_new(self) -> None:
        scene = SceneModel(placements={})
        client = _make_test_app(scene)
        resp = client.put(
            "/api/scene/devices/new_lamp",
            json={
                "position": [1.0, 2.0, 0.0],
                "geometry": "point",
                "led_count": 1,
            },
        )
        assert resp.status_code == 200
        assert "new_lamp" in scene.placements
        assert resp.json()["device_id"] == "new_lamp"

    def test_update_mapping(self) -> None:
        scene = SceneModel(
            placements={
                "lamp": DevicePlacement("lamp", (0.0, 0.0, 0.0), PointGeometry(), 1),
            }
        )
        client = _make_test_app(scene)
        resp = client.put(
            "/api/scene/mapping", json={"type": "radial", "params": {"center": [0, 0, 0]}}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "radial"

    def test_compositor_rebuilt_after_mutation(self) -> None:
        scene = SceneModel(
            placements={
                "lamp": DevicePlacement("lamp", (0.0, 0.0, 0.0), PointGeometry(), 1),
            }
        )
        mock_config = MagicMock()
        mock_config.web.cors_origins = ["*"]
        mock_config.web.static_dir = None
        mock_config.scene_config = {"mapping": "linear", "mapping_params": {}}
        mock_scheduler = MagicMock()

        app = create_app(
            beat_clock=MagicMock(),
            effect_deck=MagicMock(),
            effect_engine=MagicMock(),
            device_manager=MagicMock(),
            scheduler=mock_scheduler,
            preset_store=MagicMock(),
            scene_model=scene,
            compositor=SpatialCompositor(scene, LinearMapping()),
            config=mock_config,
            config_path=None,
        )
        client = TestClient(app)
        client.put("/api/scene/devices/lamp", json={"position": [5.0, 0.0, 0.0]})
        assert mock_scheduler.compositor is not None

    def test_get_scene_no_scene_model(self) -> None:
        client = _make_test_app(None)
        resp = client.get("/api/scene")
        assert resp.status_code == 200
        data = resp.json()
        assert data["placements"] == []

    def test_put_device_auto_creates_scene_when_none(self) -> None:
        """Adding a device when no scene exists should auto-create one."""
        client = _make_test_app(None)
        resp = client.put(
            "/api/scene/devices/lamp",
            json={"position": [0.0, 0.0, 0.0], "geometry": "point", "led_count": 1},
        )
        assert resp.status_code == 200
        assert resp.json()["device_id"] == "lamp"


class TestMultiSceneEndpoints:
    """Tests for multi-scene CRUD endpoints (require StateDB)."""

    def _make_db_client(self, tmp_path, with_pipeline_manager=True):
        if not with_pipeline_manager:
            db = StateDB(tmp_path / "state.db")
            asyncio.run(db.open())
            client = _make_test_app(state_db=db, pipeline_manager=None)
            return client, db
        client, db, _ = _make_db_client(tmp_path)
        return client, db

    def test_list_scenes_empty(self, tmp_path) -> None:
        client, db = self._make_db_client(tmp_path)
        try:
            resp = client.get("/api/scenes")
            assert resp.status_code == 200
            assert resp.json() == []
        finally:
            asyncio.run(db.close())

    def test_create_scene(self, tmp_path) -> None:
        client, db = self._make_db_client(tmp_path)
        try:
            resp = client.post("/api/scenes", json={"name": "Main Stage"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["name"] == "Main Stage"
            assert "id" in data
        finally:
            asyncio.run(db.close())

    def test_get_scene_by_id(self, tmp_path) -> None:
        client, db = self._make_db_client(tmp_path)
        try:
            created = client.post("/api/scenes", json={"name": "Stage"}).json()
            scene_id = created["id"]
            resp = client.get(f"/api/scenes/{scene_id}")
            assert resp.status_code == 200
            assert resp.json()["name"] == "Stage"
        finally:
            asyncio.run(db.close())

    def test_get_scene_not_found(self, tmp_path) -> None:
        client, db = self._make_db_client(tmp_path)
        try:
            resp = client.get("/api/scenes/nonexistent-id")
            assert resp.status_code == 404
        finally:
            asyncio.run(db.close())

    def test_update_scene(self, tmp_path) -> None:
        client, db = self._make_db_client(tmp_path)
        try:
            created = client.post("/api/scenes", json={"name": "Old Name"}).json()
            scene_id = created["id"]
            resp = client.put(f"/api/scenes/{scene_id}", json={"name": "New Name"})
            assert resp.status_code == 200
            assert resp.json()["name"] == "New Name"
        finally:
            asyncio.run(db.close())

    def test_delete_scene(self, tmp_path) -> None:
        client, db = self._make_db_client(tmp_path)
        try:
            created = client.post("/api/scenes", json={"name": "Temp"}).json()
            scene_id = created["id"]
            resp = client.delete(f"/api/scenes/{scene_id}")
            assert resp.status_code == 200
            assert resp.json()["status"] == "deleted"
            # Verify gone
            resp2 = client.get(f"/api/scenes/{scene_id}")
            assert resp2.status_code == 404
        finally:
            asyncio.run(db.close())

    def test_activate_scene(self, tmp_path) -> None:
        client, db = self._make_db_client(tmp_path)
        try:
            created = client.post("/api/scenes", json={"name": "Show"}).json()
            scene_id = created["id"]
            resp = client.post(f"/api/scenes/{scene_id}/activate")
            assert resp.status_code == 200
            assert resp.json()["scene_id"] == scene_id
        finally:
            asyncio.run(db.close())

    def test_deactivate_scene(self, tmp_path) -> None:
        client, db = self._make_db_client(tmp_path)
        try:
            created = client.post("/api/scenes", json={"name": "Show"}).json()
            scene_id = created["id"]
            client.post(f"/api/scenes/{scene_id}/activate")
            resp = client.post(f"/api/scenes/{scene_id}/deactivate")
            assert resp.status_code == 200
            assert resp.json()["scene_id"] == scene_id
        finally:
            asyncio.run(db.close())

    def test_add_device_to_scene(self, tmp_path) -> None:
        client, db = self._make_db_client(tmp_path)
        try:
            created = client.post("/api/scenes", json={"name": "Stage"}).json()
            scene_id = created["id"]
            resp = client.put(
                f"/api/scenes/{scene_id}/devices/strip1",
                json={"position": [1.0, 0.0, 0.0], "geometry": "strip", "length": 2.0},
            )
            assert resp.status_code == 200
            assert resp.json()["device_id"] == "strip1"
        finally:
            asyncio.run(db.close())

    def test_remove_device_from_scene(self, tmp_path) -> None:
        client, db = self._make_db_client(tmp_path)
        try:
            created = client.post("/api/scenes", json={"name": "Stage"}).json()
            scene_id = created["id"]
            client.put(
                f"/api/scenes/{scene_id}/devices/lamp",
                json={"position": [0.0, 0.0, 0.0], "geometry": "point"},
            )
            resp = client.delete(f"/api/scenes/{scene_id}/devices/lamp")
            assert resp.status_code == 200
            assert resp.json()["device_name"] == "lamp"
        finally:
            asyncio.run(db.close())

    def test_list_scenes_no_db_fallback(self) -> None:
        """Without DB, list_scenes returns in-memory scene."""
        scene = SceneModel(placements={})
        client = _make_test_app(scene, state_db=None)
        resp = client.get("/api/scenes")
        assert resp.status_code == 200

    def test_create_scene_no_db(self) -> None:
        """Without DB, create_scene returns 503."""
        client = _make_test_app(None)
        resp = client.post("/api/scenes", json={"name": "Test"})
        assert resp.status_code == 503

    def test_activate_scene_conflict_returns_409(self, tmp_path) -> None:
        """Activating a scene whose device is already in another active scene returns 409."""
        client, db = _make_real_device_client(
            tmp_path, name="shared_strip", stable_id="lifx:shared"
        )
        try:
            # Create two scenes, both containing the same device
            scene1 = client.post("/api/scenes", json={"name": "Scene One"}).json()
            scene2 = client.post("/api/scenes", json={"name": "Scene Two"}).json()
            scene1_id = scene1["id"]
            scene2_id = scene2["id"]

            # Add the shared device to both scenes (endpoint resolves to stable_id via manager)
            client.put(
                f"/api/scenes/{scene1_id}/devices/shared_strip",
                json={"position": [0.0, 0.0, 0.0], "geometry": "point"},
            )
            client.put(
                f"/api/scenes/{scene2_id}/devices/shared_strip",
                json={"position": [1.0, 0.0, 0.0], "geometry": "point"},
            )

            # Activate scene 1 — should succeed
            resp1 = client.post(f"/api/scenes/{scene1_id}/activate")
            assert resp1.status_code == 200

            # Activate scene 2 — should fail with 409
            resp2 = client.post(f"/api/scenes/{scene2_id}/activate")
            assert resp2.status_code == 409
            detail = resp2.json()["detail"]
            assert "conflicting_devices" in detail
            assert "lifx:shared" in detail["conflicting_devices"]
        finally:
            asyncio.run(db.close())

    def test_activate_scene_no_conflict_both_succeed(self, tmp_path) -> None:
        """Two scenes with different devices can both be activated without conflict."""
        client, db = self._make_db_client(tmp_path)
        try:
            # Register two distinct devices
            asyncio.run(
                db.upsert_device({"id": "lifx:strip_a", "name": "strip_a", "backend": "lifx"})
            )
            asyncio.run(
                db.upsert_device({"id": "lifx:strip_b", "name": "strip_b", "backend": "lifx"})
            )

            scene1 = client.post("/api/scenes", json={"name": "Scene A"}).json()
            scene2 = client.post("/api/scenes", json={"name": "Scene B"}).json()
            scene1_id = scene1["id"]
            scene2_id = scene2["id"]

            client.put(
                f"/api/scenes/{scene1_id}/devices/strip_a",
                json={"position": [0.0, 0.0, 0.0], "geometry": "point"},
            )
            client.put(
                f"/api/scenes/{scene2_id}/devices/strip_b",
                json={"position": [1.0, 0.0, 0.0], "geometry": "point"},
            )

            resp1 = client.post(f"/api/scenes/{scene1_id}/activate")
            assert resp1.status_code == 200

            resp2 = client.post(f"/api/scenes/{scene2_id}/activate")
            assert resp2.status_code == 200
        finally:
            asyncio.run(db.close())

    def test_deactivate_does_not_affect_other_scenes(self, tmp_path) -> None:
        """Deactivating one scene leaves other active scenes untouched."""
        client, db = self._make_db_client(tmp_path)
        try:
            # Register two distinct devices so both scenes can be activated
            asyncio.run(db.upsert_device({"id": "lifx:dev_x", "name": "dev_x", "backend": "lifx"}))
            asyncio.run(db.upsert_device({"id": "lifx:dev_y", "name": "dev_y", "backend": "lifx"}))

            scene1 = client.post("/api/scenes", json={"name": "Keep Active"}).json()
            scene2 = client.post("/api/scenes", json={"name": "To Deactivate"}).json()
            scene1_id = scene1["id"]
            scene2_id = scene2["id"]

            client.put(
                f"/api/scenes/{scene1_id}/devices/dev_x",
                json={"position": [0.0, 0.0, 0.0], "geometry": "point"},
            )
            client.put(
                f"/api/scenes/{scene2_id}/devices/dev_y",
                json={"position": [1.0, 0.0, 0.0], "geometry": "point"},
            )

            # Activate both scenes
            client.post(f"/api/scenes/{scene1_id}/activate")
            client.post(f"/api/scenes/{scene2_id}/activate")

            # Deactivate scene 2 only
            resp = client.post(f"/api/scenes/{scene2_id}/deactivate")
            assert resp.status_code == 200
            assert resp.json()["scene_id"] == scene2_id

            # Scene 1 must still be active
            scene1_row = client.get(f"/api/scenes/{scene1_id}").json()
            assert scene1_row["is_active"] is True

            # Scene 2 must now be inactive
            scene2_row = client.get(f"/api/scenes/{scene2_id}").json()
            assert scene2_row["is_active"] is False
        finally:
            asyncio.run(db.close())

    def test_placement_stores_stable_id_returns_display_name(self, tmp_path) -> None:
        """PUT placement stores stable_id in DB but returns display name in the response."""
        client, db = _make_real_device_client(tmp_path)
        try:
            scene = client.post("/api/scenes", json={"name": "Test Scene"}).json()
            scene_id = scene["id"]

            resp = client.put(
                f"/api/scenes/{scene_id}/devices/My Strip",
                json={"position": [2.0, 0.0, 0.0], "geometry": "point"},
            )
            assert resp.status_code == 200

            # The response device_id should be the display name (matches GET /api/scenes/{id})
            assert resp.json()["device_id"] == "My Strip"

            # The DB placement record must use the stable_id (not the display name)
            placements = asyncio.run(db.load_scene_placements(scene_id))
            assert len(placements) == 1
            assert placements[0]["device_id"] == "lifx:my_strip"
        finally:
            asyncio.run(db.close())

    def test_activate_scene_calls_pipeline_manager(self, tmp_path) -> None:
        """activate endpoint should call pipeline_manager.activate_scene."""
        client, db = self._make_db_client(tmp_path)
        try:
            resp = client.post("/api/scenes", json={"name": "TestScene"})
            scene_id = resp.json()["id"]
            resp = client.post(f"/api/scenes/{scene_id}/activate")
            assert resp.status_code == 200

            pm = client.app.state.pipeline_manager
            pm.activate_scene.assert_called_once_with(scene_id)
        finally:
            asyncio.run(db.close())

    def test_deactivate_scene_calls_pipeline_manager(self, tmp_path) -> None:
        """deactivate endpoint should call pipeline_manager.deactivate_scene."""
        client, db = self._make_db_client(tmp_path)
        try:
            resp = client.post("/api/scenes", json={"name": "TestScene"})
            scene_id = resp.json()["id"]
            client.post(f"/api/scenes/{scene_id}/activate")

            resp = client.post(f"/api/scenes/{scene_id}/deactivate")
            assert resp.status_code == 200

            pm = client.app.state.pipeline_manager
            pm.deactivate_scene.assert_called_once_with(scene_id)
        finally:
            asyncio.run(db.close())

    def test_delete_active_scene_deactivates_first(self, tmp_path) -> None:
        """Deleting an active scene should deactivate it first."""
        client, db = self._make_db_client(tmp_path)
        try:
            resp = client.post("/api/scenes", json={"name": "TestScene"})
            scene_id = resp.json()["id"]
            client.post(f"/api/scenes/{scene_id}/activate")

            resp = client.delete(f"/api/scenes/{scene_id}")
            assert resp.status_code == 200

            pm = client.app.state.pipeline_manager
            pm.deactivate_scene.assert_called_once_with(scene_id)
        finally:
            asyncio.run(db.close())

    def test_get_scene_effect(self, tmp_path) -> None:
        client, db = self._make_db_client(tmp_path)
        try:
            resp = client.post("/api/scenes", json={"name": "TestScene"})
            scene_id = resp.json()["id"]

            pm = client.app.state.pipeline_manager
            pm.get_scene_effect.return_value = {"effect_name": "beat_pulse", "params": {}}

            resp = client.get(f"/api/scenes/{scene_id}/effect")
            assert resp.status_code == 200
            assert resp.json()["effect_name"] == "beat_pulse"
        finally:
            asyncio.run(db.close())

    def test_put_scene_effect(self, tmp_path) -> None:
        client, db = self._make_db_client(tmp_path)
        try:
            resp = client.post("/api/scenes", json={"name": "TestScene"})
            scene_id = resp.json()["id"]

            pm = client.app.state.pipeline_manager
            pm.set_scene_effect.return_value = {"wave_count": 3.0}

            resp = client.put(
                f"/api/scenes/{scene_id}/effect",
                json={"effect_name": "rainbow_wave", "params": {}},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["scene_id"] == scene_id
            assert data["effect_name"] == "rainbow_wave"
            assert data["params"] == {"wave_count": 3.0}
            pm.set_scene_effect.assert_called_once_with(scene_id, "rainbow_wave", {})
        finally:
            asyncio.run(db.close())

    def test_put_scene_effect_no_pipeline_manager(self, tmp_path) -> None:
        """Without pipeline_manager, scene effect endpoints return 501."""
        client, db = self._make_db_client(tmp_path, with_pipeline_manager=False)
        try:
            resp = client.put(
                "/api/scenes/fake/effect",
                json={"effect_name": "beat_pulse", "params": {}},
            )
            assert resp.status_code == 501
        finally:
            asyncio.run(db.close())

    def test_update_active_scene_effect_mode_returns_409(self, tmp_path) -> None:
        client, db = self._make_db_client(tmp_path)
        try:
            resp = client.post(
                "/api/scenes", json={"name": "TestScene", "effect_mode": "independent"}
            )
            scene_id = resp.json()["id"]
            client.post(f"/api/scenes/{scene_id}/activate")

            resp = client.put(
                f"/api/scenes/{scene_id}",
                json={"name": "TestScene", "effect_mode": "shared"},
            )
            assert resp.status_code == 409
        finally:
            asyncio.run(db.close())

    def test_remove_placement_resolves_stable_id(self, tmp_path) -> None:
        """DELETE /api/scenes/{id}/devices/{name} resolves display name to stable_id."""
        client, db = _make_real_device_client(tmp_path)
        try:
            scene = client.post("/api/scenes", json={"name": "Test Scene"}).json()
            scene_id = scene["id"]

            # Add placement via display name — stored under lifx:my_strip
            resp = client.put(
                f"/api/scenes/{scene_id}/devices/My Strip",
                json={"position": [2.0, 0.0, 0.0], "geometry": "point"},
            )
            assert resp.status_code == 200
            assert resp.json()["device_id"] == "My Strip"  # response returns display name

            # Delete via display name — must resolve to stable_id
            resp = client.delete(f"/api/scenes/{scene_id}/devices/My Strip")
            assert resp.status_code == 200

            # Placement must be gone
            placements = asyncio.run(db.load_scene_placements(scene_id))
            assert placements == []
        finally:
            asyncio.run(db.close())


class TestSceneDetail:
    """Tests for GET /api/scenes/{id} returning full SceneDetail."""

    def _make_real_device_client(self, tmp_path):
        return _make_real_device_client(tmp_path)

    def test_get_scene_detail_includes_placements_and_mapping(self, tmp_path) -> None:
        client, db = self._make_real_device_client(tmp_path)
        try:
            scene_id = client.post("/api/scenes", json={"name": "A"}).json()["id"]
            client.put(
                f"/api/scenes/{scene_id}/devices/My Strip",
                json={
                    "position": [1.0, 2.0, 3.0],
                    "geometry": "strip",
                    "direction": [1, 0, 0],
                    "length": 2.0,
                },
            )
            client.put(
                f"/api/scenes/{scene_id}",
                json={"mapping_type": "radial", "mapping_params": {"center": [0, 0, 0]}},
            )
            detail = client.get(f"/api/scenes/{scene_id}").json()
            assert detail["name"] == "A"
            assert len(detail["placements"]) == 1
            p = detail["placements"][0]
            assert p["device_id"] == "My Strip"  # display name, not stable_id
            assert p["position"] == [1.0, 2.0, 3.0]
            assert p["geometry"]["type"] == "strip"
            assert p["led_count"] == 30  # from adapter, not DB
            assert p["strip_index"] is not None
            assert detail["mapping"] == {"type": "radial", "params": {"center": [0.0, 0.0, 0.0]}}
            assert detail["bounds"] is not None
        finally:
            asyncio.run(db.close())

    def test_get_scene_detail_unknown_device_falls_back_to_stable_id(self, tmp_path) -> None:
        # plain _make_db_client (device_manager bare MagicMock -> no resolution)
        client, db, _ = _make_db_client(tmp_path)
        try:
            scene_id = client.post("/api/scenes", json={"name": "A"}).json()["id"]
            client.put(f"/api/scenes/{scene_id}/devices/ghost", json={"position": [0, 0, 0]})
            detail = client.get(f"/api/scenes/{scene_id}").json()
            assert detail["placements"][0]["device_id"] == "ghost"
            # A fresh scene with no mapping_type set must return mapping=None
            assert detail["mapping"] is None
        finally:
            asyncio.run(db.close())

    def test_update_scene_persists_mapping_params(self, tmp_path) -> None:
        client, db, _ = _make_db_client(tmp_path)
        try:
            scene_id = client.post("/api/scenes", json={"name": "A"}).json()["id"]
            client.put(f"/api/scenes/{scene_id}", json={"mapping_params": {"origin": [1, 1, 1]}})
            detail = client.get(f"/api/scenes/{scene_id}").json()
            assert detail["mapping"]["params"] == {"origin": [1.0, 1.0, 1.0]}
            client.put(f"/api/scenes/{scene_id}", json={"name": "B"})  # must not wipe params
            detail = client.get(f"/api/scenes/{scene_id}").json()
            assert detail["mapping"]["params"] == {"origin": [1.0, 1.0, 1.0]}
        finally:
            asyncio.run(db.close())

    def test_get_scene_detail_preserves_zero_direction_components(self, tmp_path) -> None:
        """A stored direction of [0, 1, 0] must not be coerced to [1, 1, 0] by falsy-zero or."""
        client, db = self._make_real_device_client(tmp_path)
        try:
            scene_id = client.post("/api/scenes", json={"name": "A"}).json()["id"]
            client.put(
                f"/api/scenes/{scene_id}/devices/My Strip",
                json={
                    "position": [0.0, 0.0, 0.0],
                    "geometry": "strip",
                    "direction": [0, 1, 0],
                    "length": 2.0,
                },
            )
            detail = client.get(f"/api/scenes/{scene_id}").json()
            assert len(detail["placements"]) == 1
            direction = detail["placements"][0]["geometry"]["direction"]
            assert direction[0] == pytest.approx(0.0), "x component must not be coerced to 1.0"
            assert direction[1] == pytest.approx(1.0), "y component must be preserved"
            assert direction[2] == pytest.approx(0.0)
        finally:
            asyncio.run(db.close())

    def test_invalid_mapping_params_rejected_and_get_survives(self, tmp_path) -> None:
        client, db, _ = _make_db_client(tmp_path)
        try:
            scene_id = client.post("/api/scenes", json={"name": "A"}).json()["id"]
            # Bad mapping_params (zero direction vector) must be rejected.
            resp = client.put(
                f"/api/scenes/{scene_id}",
                json={"mapping_params": {"direction": [0, 0, 0]}},
            )
            assert resp.status_code == 422
            # Scene GET must still work — bad params were never persisted.
            assert client.get(f"/api/scenes/{scene_id}").status_code == 200

            # Read-guard: seed bad params directly into DB bypassing validation.
            existing = asyncio.run(db.load_scene_by_id(scene_id))
            assert existing is not None
            bad_row = dict(existing)
            bad_row["mapping_params"] = '{"direction": [0, 0, 0]}'
            asyncio.run(db.save_scene(bad_row))
            # Add a placement so the compositor path is exercised.
            asyncio.run(db.upsert_device({"id": "d1", "name": "d1", "backend": "mock"}))
            asyncio.run(
                db.save_placement(
                    {
                        "scene_id": scene_id,
                        "device_id": "d1",
                        "position_x": 0.0,
                        "position_y": 0.0,
                        "position_z": 0.0,
                        "geometry_type": "point",
                    }
                )
            )
            # GET must degrade gracefully: 200 with strip_index None.
            resp = client.get(f"/api/scenes/{scene_id}")
            assert resp.status_code == 200
            placements = resp.json()["placements"]
            assert len(placements) == 1
            assert placements[0]["strip_index"] is None
        finally:
            asyncio.run(db.close())


class TestActivateHardening:
    """Tests for idempotent activation and 409 on pipeline build failure."""

    def _make_db_client_with_pm(self, tmp_path, pm_mock):
        client, db, _ = _make_db_client(tmp_path, pm=pm_mock)
        return client, db

    def test_activate_already_active_returns_200(self, tmp_path) -> None:
        """Re-activating an already-active scene returns 200 with status already_active."""
        pm = MagicMock()
        pm.activate_scene = AsyncMock()
        pm.deactivate_scene = AsyncMock()
        pm.is_scene_active.return_value = True

        client, db = self._make_db_client_with_pm(tmp_path, pm)
        try:
            resp = client.post("/api/scenes", json={"name": "Show"})
            scene_id = resp.json()["id"]

            resp = client.post(f"/api/scenes/{scene_id}/activate")
            assert resp.status_code == 200
            assert resp.json()["status"] == "already_active"
            pm.activate_scene.assert_not_called()
            assert client.get(f"/api/scenes/{scene_id}").json()["is_active"] is True
        finally:
            asyncio.run(db.close())

    def test_activate_pipeline_failure_returns_409_and_db_unchanged(self, tmp_path) -> None:
        """A pipeline build failure raises 409 and leaves is_active=False in DB."""
        pm = MagicMock()
        pm.activate_scene = AsyncMock(side_effect=ValueError("Could not build pipeline"))
        pm.deactivate_scene = AsyncMock()
        pm.is_scene_active.return_value = False

        client, db = self._make_db_client_with_pm(tmp_path, pm)
        try:
            resp = client.post("/api/scenes", json={"name": "Broken"})
            scene_id = resp.json()["id"]

            resp = client.post(f"/api/scenes/{scene_id}/activate")
            assert resp.status_code == 409

            # DB must still show is_active=False (atomicity invariant)
            scene_row = client.get(f"/api/scenes/{scene_id}").json()
            assert scene_row["is_active"] is False
        finally:
            asyncio.run(db.close())
