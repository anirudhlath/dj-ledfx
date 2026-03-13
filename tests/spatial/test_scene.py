from __future__ import annotations

import numpy as np

from dj_ledfx.spatial.geometry import (
    PointGeometry,
    StripGeometry,
)
from dj_ledfx.spatial.scene import DevicePlacement, SceneModel
from tests.conftest import MockDeviceAdapter


class TestDevicePlacement:
    def test_create(self) -> None:
        p = DevicePlacement(
            device_id="lamp",
            position=(1.0, 2.0, 3.0),
            geometry=PointGeometry(),
            led_count=1,
        )
        assert p.device_id == "lamp"
        assert p.led_count == 1


class TestSceneModel:
    def test_get_led_positions_point(self) -> None:
        scene = SceneModel(placements={
            "bulb": DevicePlacement("bulb", (1.0, 2.0, 0.0), PointGeometry(), 1),
        })
        pos = scene.get_led_positions("bulb")
        assert pos.shape == (1, 3)
        np.testing.assert_array_almost_equal(pos[0], [1.0, 2.0, 0.0])

    def test_get_led_positions_strip(self) -> None:
        geo = StripGeometry(direction=(1.0, 0.0, 0.0), length=1.0)
        scene = SceneModel(placements={
            "strip": DevicePlacement("strip", (0.0, 0.0, 0.0), geo, 4),
        })
        pos = scene.get_led_positions("strip")
        assert pos.shape == (4, 3)

    def test_get_led_positions_cached(self) -> None:
        scene = SceneModel(placements={
            "bulb": DevicePlacement("bulb", (1.0, 2.0, 0.0), PointGeometry(), 1),
        })
        pos1 = scene.get_led_positions("bulb")
        pos2 = scene.get_led_positions("bulb")
        assert pos1 is pos2  # same object, cached

    def test_get_bounds(self) -> None:
        scene = SceneModel(placements={
            "a": DevicePlacement("a", (0.0, 0.0, 0.0), PointGeometry(), 1),
            "b": DevicePlacement("b", (10.0, 5.0, 3.0), PointGeometry(), 1),
        })
        bounds_min, bounds_max = scene.get_bounds()
        np.testing.assert_array_almost_equal(bounds_min, [0.0, 0.0, 0.0])
        np.testing.assert_array_almost_equal(bounds_max, [10.0, 5.0, 3.0])

    def test_from_config_point_device(self) -> None:
        adapters = [MockDeviceAdapter(name="lamp", led_count=1)]
        config = {
            "devices": [
                {"name": "lamp", "position": [1.0, 2.0, 0.0], "geometry": "point"},
            ],
        }
        scene = SceneModel.from_config(config, adapters)
        assert "lamp" in scene.placements
        assert scene.placements["lamp"].led_count == 1

    def test_from_config_strip_device(self) -> None:
        adapters = [MockDeviceAdapter(name="strip", led_count=30)]
        config = {
            "devices": [
                {
                    "name": "strip",
                    "position": [0.0, 0.0, 0.0],
                    "geometry": "strip",
                    "direction": [1.0, 0.0, 0.0],
                    "length": 1.5,
                },
            ],
        }
        scene = SceneModel.from_config(config, adapters)
        assert "strip" in scene.placements
        assert scene.placements["strip"].led_count == 30

    def test_from_config_adapter_geometry_used(self) -> None:
        geo = PointGeometry()
        adapters = [MockDeviceAdapter(name="bulb", led_count=1, geometry=geo)]
        config = {
            "devices": [
                {"name": "bulb", "position": [0.0, 0.0, 0.0]},
            ],
        }
        scene = SceneModel.from_config(config, adapters)
        assert isinstance(scene.placements["bulb"].geometry, PointGeometry)

    def test_from_config_config_geometry_overrides_adapter(self) -> None:
        geo = PointGeometry()
        adapters = [MockDeviceAdapter(name="dev", led_count=10, geometry=geo)]
        config = {
            "devices": [
                {
                    "name": "dev",
                    "position": [0.0, 0.0, 0.0],
                    "geometry": "strip",
                    "direction": [1.0, 0.0, 0.0],
                    "length": 1.0,
                },
            ],
        }
        scene = SceneModel.from_config(config, adapters)
        assert isinstance(scene.placements["dev"].geometry, StripGeometry)

    def test_from_config_unknown_device_skipped(self) -> None:
        adapters = [MockDeviceAdapter(name="real_device", led_count=1)]
        config = {
            "devices": [
                {"name": "nonexistent", "position": [0.0, 0.0, 0.0], "geometry": "point"},
            ],
        }
        scene = SceneModel.from_config(config, adapters)
        assert len(scene.placements) == 0

    def test_from_config_bad_position_skipped(self) -> None:
        adapters = [MockDeviceAdapter(name="dev", led_count=1)]
        config = {
            "devices": [
                {"name": "dev", "position": [0.0, 0.0], "geometry": "point"},
            ],
        }
        scene = SceneModel.from_config(config, adapters)
        assert len(scene.placements) == 0

    def test_from_config_fallback_geometry(self) -> None:
        adapters = [MockDeviceAdapter(name="dev", led_count=10)]
        config = {
            "devices": [
                {"name": "dev", "position": [0.0, 0.0, 0.0]},
            ],
        }
        scene = SceneModel.from_config(config, adapters)
        # >1 LED, no geometry specified, no adapter geometry → StripGeometry fallback
        assert isinstance(scene.placements["dev"].geometry, StripGeometry)

    def test_from_config_single_led_fallback_to_point(self) -> None:
        adapters = [MockDeviceAdapter(name="dev", led_count=1)]
        config = {
            "devices": [
                {"name": "dev", "position": [0.0, 0.0, 0.0]},
            ],
        }
        scene = SceneModel.from_config(config, adapters)
        assert isinstance(scene.placements["dev"].geometry, PointGeometry)

    def test_from_config_backend_prefix_match(self) -> None:
        adapters = [MockDeviceAdapter(name="DJ Booth", led_count=1)]
        config = {
            "devices": [
                {"name": "lifx:DJ Booth", "position": [0.0, 0.0, 0.0], "geometry": "point"},
            ],
        }
        scene = SceneModel.from_config(config, adapters)
        # Should match by stripping "lifx:" prefix
        assert "DJ Booth" in scene.placements

    def test_from_config_duplicate_name_last_wins(self) -> None:
        adapters = [MockDeviceAdapter(name="dev", led_count=1)]
        config = {
            "devices": [
                {"name": "dev", "position": [0.0, 0.0, 0.0], "geometry": "point"},
                {"name": "dev", "position": [5.0, 5.0, 5.0], "geometry": "point"},
            ],
        }
        scene = SceneModel.from_config(config, adapters)
        assert scene.placements["dev"].position == (5.0, 5.0, 5.0)

    def test_from_config_strip_missing_length_defaults(self) -> None:
        adapters = [MockDeviceAdapter(name="strip", led_count=10)]
        config = {
            "devices": [
                {
                    "name": "strip",
                    "position": [0.0, 0.0, 0.0],
                    "geometry": "strip",
                    "direction": [1.0, 0.0, 0.0],
                },
            ],
        }
        scene = SceneModel.from_config(config, adapters)
        geo = scene.placements["strip"].geometry
        assert isinstance(geo, StripGeometry)
        assert geo.length == 1.0
