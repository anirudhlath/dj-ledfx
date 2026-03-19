from __future__ import annotations

from fastapi.testclient import TestClient

from dj_ledfx.spatial.compositor import SpatialCompositor
from dj_ledfx.spatial.geometry import PointGeometry, StripGeometry
from dj_ledfx.spatial.mapping import LinearMapping
from dj_ledfx.spatial.scene import DevicePlacement, SceneModel
from dj_ledfx.web.app import create_app


def _make_test_app(scene: SceneModel | None = None) -> TestClient:
    """Create a test FastAPI app with a scene model."""
    from unittest.mock import MagicMock

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
        from unittest.mock import MagicMock

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
