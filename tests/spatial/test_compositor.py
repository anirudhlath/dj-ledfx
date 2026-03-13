from __future__ import annotations

import numpy as np

from dj_ledfx.spatial.compositor import SpatialCompositor
from dj_ledfx.spatial.geometry import MatrixGeometry, PointGeometry, StripGeometry, TileLayout
from dj_ledfx.spatial.mapping import LinearMapping, RadialMapping
from dj_ledfx.spatial.scene import DevicePlacement, SceneModel


def _gradient_strip(n: int) -> np.ndarray:
    """Create a gradient from black (0,0,0) to white (255,255,255)."""
    t = np.linspace(0, 255, n, dtype=np.uint8)
    return np.column_stack([t, t, t])


class TestSpatialCompositor:
    def test_point_device_gets_single_color(self) -> None:
        scene = SceneModel(placements={
            "bulb": DevicePlacement("bulb", (0.5, 0.0, 0.0), PointGeometry(), 1),
        })
        mapping = LinearMapping(direction=(1.0, 0.0, 0.0))
        comp = SpatialCompositor(scene, mapping)
        strip = _gradient_strip(256)
        result = comp.composite(strip, "bulb")
        assert result is not None
        assert result.shape == (1, 3)

    def test_devices_at_different_positions_get_different_colors(self) -> None:
        scene = SceneModel(placements={
            "left": DevicePlacement("left", (0.0, 0.0, 0.0), PointGeometry(), 1),
            "right": DevicePlacement("right", (10.0, 0.0, 0.0), PointGeometry(), 1),
        })
        mapping = LinearMapping(direction=(1.0, 0.0, 0.0))
        comp = SpatialCompositor(scene, mapping)
        strip = _gradient_strip(256)
        left_colors = comp.composite(strip, "left")
        right_colors = comp.composite(strip, "right")
        assert left_colors is not None
        assert right_colors is not None
        # Left should be darker than right along the gradient
        assert left_colors[0, 0] < right_colors[0, 0]

    def test_strip_device_gets_gradient(self) -> None:
        geo = StripGeometry(direction=(1.0, 0.0, 0.0), length=10.0)
        scene = SceneModel(placements={
            "strip": DevicePlacement("strip", (0.0, 0.0, 0.0), geo, 10),
        })
        mapping = LinearMapping(direction=(1.0, 0.0, 0.0))
        comp = SpatialCompositor(scene, mapping)
        strip = _gradient_strip(256)
        result = comp.composite(strip, "strip")
        assert result is not None
        assert result.shape == (10, 3)
        # Colors should increase along the strip
        assert np.all(np.diff(result[:, 0].astype(int)) >= 0)

    def test_matrix_device(self) -> None:
        tile = TileLayout(offset_x=0.0, offset_y=0.0, width=4, height=4)
        geo = MatrixGeometry(tiles=(tile,), pixel_pitch=1.0)
        scene = SceneModel(placements={
            "tiles": DevicePlacement("tiles", (0.0, 0.0, 0.0), geo, 16),
        })
        mapping = LinearMapping(direction=(1.0, 0.0, 0.0))
        comp = SpatialCompositor(scene, mapping)
        strip = _gradient_strip(256)
        result = comp.composite(strip, "tiles")
        assert result is not None
        assert result.shape == (16, 3)

    def test_unknown_device_returns_none(self) -> None:
        scene = SceneModel(placements={})
        mapping = LinearMapping()
        comp = SpatialCompositor(scene, mapping)
        strip = _gradient_strip(256)
        result = comp.composite(strip, "nonexistent")
        assert result is None

    def test_radial_mapping_integration(self) -> None:
        scene = SceneModel(placements={
            "center": DevicePlacement("center", (0.0, 0.0, 0.0), PointGeometry(), 1),
            "edge": DevicePlacement("edge", (5.0, 0.0, 0.0), PointGeometry(), 1),
        })
        mapping = RadialMapping(center=(0.0, 0.0, 0.0))
        comp = SpatialCompositor(scene, mapping)
        strip = _gradient_strip(256)
        center_colors = comp.composite(strip, "center")
        edge_colors = comp.composite(strip, "edge")
        assert center_colors is not None
        assert edge_colors is not None
        assert center_colors[0, 0] < edge_colors[0, 0]
