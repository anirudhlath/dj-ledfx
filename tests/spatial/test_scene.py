from __future__ import annotations

import numpy as np
import pytest

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
        scene = SceneModel(
            placements={
                "bulb": DevicePlacement("bulb", (1.0, 2.0, 0.0), PointGeometry(), 1),
            }
        )
        pos = scene.get_led_positions("bulb")
        assert pos.shape == (1, 3)
        np.testing.assert_array_almost_equal(pos[0], [1.0, 2.0, 0.0])

    def test_get_led_positions_strip(self) -> None:
        geo = StripGeometry(direction=(1.0, 0.0, 0.0), length=1.0)
        scene = SceneModel(
            placements={
                "strip": DevicePlacement("strip", (0.0, 0.0, 0.0), geo, 4),
            }
        )
        pos = scene.get_led_positions("strip")
        assert pos.shape == (4, 3)

    def test_get_led_positions_cached(self) -> None:
        scene = SceneModel(
            placements={
                "bulb": DevicePlacement("bulb", (1.0, 2.0, 0.0), PointGeometry(), 1),
            }
        )
        pos1 = scene.get_led_positions("bulb")
        pos2 = scene.get_led_positions("bulb")
        assert pos1 is pos2  # same object, cached

    def test_get_bounds(self) -> None:
        scene = SceneModel(
            placements={
                "a": DevicePlacement("a", (0.0, 0.0, 0.0), PointGeometry(), 1),
                "b": DevicePlacement("b", (10.0, 5.0, 3.0), PointGeometry(), 1),
            }
        )
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

    def test_get_bounds_empty_scene(self) -> None:
        scene = SceneModel(placements={})
        bounds_min, bounds_max = scene.get_bounds()
        np.testing.assert_array_almost_equal(bounds_min, [0.0, 0.0, 0.0])
        np.testing.assert_array_almost_equal(bounds_max, [0.0, 0.0, 0.0])

    def test_from_config_unknown_geometry_type_skipped(self) -> None:
        adapters = [MockDeviceAdapter(name="dev", led_count=1)]
        config = {
            "devices": [
                {"name": "dev", "position": [0.0, 0.0, 0.0], "geometry": "sphere"},
            ],
        }
        scene = SceneModel.from_config(config, adapters)
        assert len(scene.placements) == 0

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


class TestSceneModelMutations:
    def test_add_placement(self) -> None:
        scene = SceneModel(placements={})
        placement = DevicePlacement("lamp", (1.0, 2.0, 0.0), PointGeometry(), 1)
        scene.add_placement(placement)
        assert "lamp" in scene.placements
        assert scene.placements["lamp"] is placement

    def test_add_placement_duplicate_raises(self) -> None:
        p = DevicePlacement("lamp", (1.0, 2.0, 0.0), PointGeometry(), 1)
        scene = SceneModel(placements={"lamp": p})
        with pytest.raises(ValueError, match="already exists"):
            scene.add_placement(p)

    def test_add_placement_invalidates_cache(self) -> None:
        scene = SceneModel(
            placements={
                "a": DevicePlacement("a", (0.0, 0.0, 0.0), PointGeometry(), 1),
            }
        )
        _ = scene.get_led_positions("a")
        assert "a" in scene._position_cache
        p = DevicePlacement("b", (5.0, 0.0, 0.0), PointGeometry(), 1)
        scene.add_placement(p)
        assert "b" not in scene._position_cache

    def test_update_placement_position(self) -> None:
        geo = PointGeometry()
        p = DevicePlacement("lamp", (0.0, 0.0, 0.0), geo, 1)
        scene = SceneModel(placements={"lamp": p})
        scene.update_placement("lamp", position=(5.0, 3.0, 1.0))
        assert scene.placements["lamp"].position == (5.0, 3.0, 1.0)
        assert scene.placements["lamp"].geometry is geo

    def test_update_placement_geometry(self) -> None:
        p = DevicePlacement("strip", (0.0, 0.0, 0.0), PointGeometry(), 10)
        scene = SceneModel(placements={"strip": p})
        new_geo = StripGeometry(direction=(0.0, 1.0, 0.0), length=2.0)
        scene.update_placement("strip", geometry=new_geo)
        assert scene.placements["strip"].geometry is new_geo
        assert scene.placements["strip"].position == (0.0, 0.0, 0.0)

    def test_update_placement_invalidates_cache(self) -> None:
        p = DevicePlacement("lamp", (0.0, 0.0, 0.0), PointGeometry(), 1)
        scene = SceneModel(placements={"lamp": p})
        _ = scene.get_led_positions("lamp")
        assert "lamp" in scene._position_cache
        scene.update_placement("lamp", position=(5.0, 0.0, 0.0))
        assert "lamp" not in scene._position_cache

    def test_update_placement_unknown_raises(self) -> None:
        scene = SceneModel(placements={})
        with pytest.raises(KeyError, match="nonexistent"):
            scene.update_placement("nonexistent", position=(0.0, 0.0, 0.0))

    def test_remove_placement(self) -> None:
        p = DevicePlacement("lamp", (0.0, 0.0, 0.0), PointGeometry(), 1)
        scene = SceneModel(placements={"lamp": p})
        scene.remove_placement("lamp")
        assert "lamp" not in scene.placements

    def test_remove_placement_clears_cache(self) -> None:
        p = DevicePlacement("lamp", (0.0, 0.0, 0.0), PointGeometry(), 1)
        scene = SceneModel(placements={"lamp": p})
        _ = scene.get_led_positions("lamp")
        assert "lamp" in scene._position_cache
        scene.remove_placement("lamp")
        assert "lamp" not in scene._position_cache

    def test_remove_placement_unknown_raises(self) -> None:
        scene = SceneModel(placements={})
        with pytest.raises(KeyError, match="nonexistent"):
            scene.remove_placement("nonexistent")
