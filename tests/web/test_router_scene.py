from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from dj_ledfx.persistence.state_db import StateDB
from dj_ledfx.spatial.compositor import SpatialCompositor
from dj_ledfx.spatial.geometry import PointGeometry, StripGeometry
from dj_ledfx.spatial.mapping import LinearMapping
from dj_ledfx.spatial.scene import DevicePlacement, SceneModel
from dj_ledfx.web.app import create_app


def _make_test_app(scene: SceneModel | None = None, state_db: StateDB | None = None) -> TestClient:
    """Create a test FastAPI app with a scene model."""
    compositor = None
    if scene and scene.placements:
        compositor = SpatialCompositor(scene, LinearMapping())

    mock_config = MagicMock()
    mock_config.web.cors_origins = ["*"]
    mock_config.web.static_dir = None
    mock_config.scene_config = None

    app = create_app(
        beat_clock=MagicMock(),
        effect_deck=MagicMock(),
        effect_engine=MagicMock(),
        device_manager=MagicMock(),
        scheduler=MagicMock(),
        preset_store=MagicMock(),
        scene_model=scene,
        compositor=compositor,
        config=mock_config,
        config_path=None,
        state_db=state_db,
    )
    return TestClient(app)


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

    def _make_db_client(self, tmp_path):
        db = StateDB(tmp_path / "state.db")
        asyncio.run(db.open())
        client = _make_test_app(state_db=db)
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
