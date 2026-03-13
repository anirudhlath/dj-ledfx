from __future__ import annotations

import numpy as np
import pytest

from dj_ledfx.spatial.geometry import (
    MatrixGeometry,
    PointGeometry,
    StripGeometry,
    TileLayout,
    expand_positions,
)


class TestPointGeometry:
    def test_create(self) -> None:
        geo = PointGeometry()
        assert geo is not None

    def test_expand_single_position(self) -> None:
        geo = PointGeometry()
        pos = (1.0, 2.0, 3.0)
        result = expand_positions(geo, pos, led_count=1)
        assert result.shape == (1, 3)
        np.testing.assert_array_almost_equal(result[0], [1.0, 2.0, 3.0])


class TestStripGeometry:
    def test_create_normalizes_direction(self) -> None:
        geo = StripGeometry(direction=(2.0, 0.0, 0.0), length=1.5)
        assert abs(sum(d * d for d in geo.direction) - 1.0) < 1e-6

    def test_unit_direction_unchanged(self) -> None:
        geo = StripGeometry(direction=(0.0, 1.0, 0.0), length=1.0)
        assert geo.direction == (0.0, 1.0, 0.0)

    def test_zero_direction_raises(self) -> None:
        with pytest.raises(ValueError, match="non-zero"):
            StripGeometry(direction=(0.0, 0.0, 0.0), length=1.0)

    def test_expand_positions_evenly_spaced(self) -> None:
        geo = StripGeometry(direction=(1.0, 0.0, 0.0), length=2.0)
        pos = (0.0, 0.0, 0.0)
        result = expand_positions(geo, pos, led_count=4)
        assert result.shape == (4, 3)
        expected_x = [0.25, 0.75, 1.25, 1.75]
        np.testing.assert_array_almost_equal(result[:, 0], expected_x)
        np.testing.assert_array_almost_equal(result[:, 1], [0.0] * 4)
        np.testing.assert_array_almost_equal(result[:, 2], [0.0] * 4)

    def test_expand_single_led_at_midpoint(self) -> None:
        geo = StripGeometry(direction=(1.0, 0.0, 0.0), length=2.0)
        pos = (0.0, 0.0, 0.0)
        result = expand_positions(geo, pos, led_count=1)
        assert result.shape == (1, 3)
        np.testing.assert_array_almost_equal(result[0], [1.0, 0.0, 0.0])

    def test_expand_with_offset_position(self) -> None:
        geo = StripGeometry(direction=(0.0, 1.0, 0.0), length=1.0)
        pos = (5.0, 3.0, 0.0)
        result = expand_positions(geo, pos, led_count=2)
        np.testing.assert_array_almost_equal(result[0], [5.0, 3.25, 0.0])
        np.testing.assert_array_almost_equal(result[1], [5.0, 3.75, 0.0])


class TestMatrixGeometry:
    def test_create(self) -> None:
        tile = TileLayout(offset_x=0.0, offset_y=0.0, width=8, height=8)
        geo = MatrixGeometry(tiles=(tile,))
        assert geo.pixel_pitch == 0.03

    def test_expand_single_tile(self) -> None:
        tile = TileLayout(offset_x=0.0, offset_y=0.0, width=2, height=2)
        geo = MatrixGeometry(tiles=(tile,), pixel_pitch=0.1)
        pos = (1.0, 2.0, 0.0)
        result = expand_positions(geo, pos, led_count=4)
        assert result.shape == (4, 3)
        np.testing.assert_array_almost_equal(result[0], [1.0, 2.0, 0.0])
        np.testing.assert_array_almost_equal(result[1], [1.1, 2.0, 0.0])
        np.testing.assert_array_almost_equal(result[2], [1.0, 2.1, 0.0])
        np.testing.assert_array_almost_equal(result[3], [1.1, 2.1, 0.0])

    def test_expand_multi_tile(self) -> None:
        tile0 = TileLayout(offset_x=0.0, offset_y=0.0, width=2, height=2)
        tile1 = TileLayout(offset_x=0.5, offset_y=0.0, width=2, height=2)
        geo = MatrixGeometry(tiles=(tile0, tile1), pixel_pitch=0.1)
        pos = (0.0, 0.0, 0.0)
        result = expand_positions(geo, pos, led_count=8)
        assert result.shape == (8, 3)
        np.testing.assert_array_almost_equal(result[4], [0.5, 0.0, 0.0])

    def test_total_led_count(self) -> None:
        t0 = TileLayout(offset_x=0.0, offset_y=0.0, width=8, height=8)
        t1 = TileLayout(offset_x=0.3, offset_y=0.0, width=8, height=8)
        geo = MatrixGeometry(tiles=(t0, t1))
        total = sum(t.width * t.height for t in geo.tiles)
        assert total == 128
