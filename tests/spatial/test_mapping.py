from __future__ import annotations

import numpy as np

from dj_ledfx.spatial.mapping import LinearMapping, RadialMapping


class TestLinearMapping:
    def test_positions_along_axis_monotonically_increasing(self) -> None:
        mapping = LinearMapping(direction=(1.0, 0.0, 0.0))
        positions = np.array([
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [2.0, 0.0, 0.0],
            [3.0, 0.0, 0.0],
        ])
        result = mapping.map_positions(positions)
        assert result.shape == (4,)
        assert np.all(np.diff(result) > 0)
        assert np.all(result >= 0.0)
        assert np.all(result <= 1.0)

    def test_positions_perpendicular_same_value(self) -> None:
        mapping = LinearMapping(direction=(1.0, 0.0, 0.0))
        positions = np.array([
            [1.0, 0.0, 0.0],
            [1.0, 5.0, 0.0],
            [1.0, -3.0, 2.0],
        ])
        result = mapping.map_positions(positions)
        np.testing.assert_array_almost_equal(result, result[0])

    def test_output_clamped_to_unit_range(self) -> None:
        mapping = LinearMapping(direction=(1.0, 0.0, 0.0))
        positions = np.array([[-100.0, 0.0, 0.0], [100.0, 0.0, 0.0]])
        result = mapping.map_positions(positions)
        assert np.all(result >= 0.0)
        assert np.all(result <= 1.0)

    def test_with_origin(self) -> None:
        mapping = LinearMapping(direction=(1.0, 0.0, 0.0), origin=(5.0, 0.0, 0.0))
        positions = np.array([[5.0, 0.0, 0.0], [10.0, 0.0, 0.0]])
        result = mapping.map_positions(positions)
        assert result[0] == 0.0

    def test_3d_diagonal_direction(self) -> None:
        mapping = LinearMapping(direction=(1.0, 1.0, 1.0))
        positions = np.array([
            [0.0, 0.0, 0.0],
            [1.0, 1.0, 1.0],
            [2.0, 2.0, 2.0],
        ])
        result = mapping.map_positions(positions)
        assert np.all(np.diff(result) > 0)

    def test_all_same_position_returns_zeros(self) -> None:
        mapping = LinearMapping(direction=(1.0, 0.0, 0.0))
        positions = np.array([[1.0, 2.0, 3.0]] * 5)
        result = mapping.map_positions(positions)
        np.testing.assert_array_almost_equal(result, 0.0)


class TestRadialMapping:
    def test_concentric_positions_increasing(self) -> None:
        mapping = RadialMapping(center=(0.0, 0.0, 0.0))
        positions = np.array([
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [2.0, 0.0, 0.0],
            [3.0, 0.0, 0.0],
        ])
        result = mapping.map_positions(positions)
        assert result.shape == (4,)
        assert np.all(np.diff(result) > 0)

    def test_equidistant_positions_same_value(self) -> None:
        mapping = RadialMapping(center=(0.0, 0.0, 0.0))
        positions = np.array([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [-1.0, 0.0, 0.0],
        ])
        result = mapping.map_positions(positions)
        np.testing.assert_array_almost_equal(result, result[0])

    def test_output_clamped(self) -> None:
        mapping = RadialMapping(center=(0.0, 0.0, 0.0), max_radius=1.0)
        positions = np.array([[0.0, 0.0, 0.0], [100.0, 0.0, 0.0]])
        result = mapping.map_positions(positions)
        assert np.all(result >= 0.0)
        assert np.all(result <= 1.0)

    def test_center_returns_zero(self) -> None:
        mapping = RadialMapping(center=(5.0, 5.0, 5.0))
        positions = np.array([[5.0, 5.0, 5.0]])
        result = mapping.map_positions(positions)
        assert result[0] == 0.0

    def test_all_at_center_returns_zeros(self) -> None:
        mapping = RadialMapping(center=(0.0, 0.0, 0.0))
        positions = np.array([[0.0, 0.0, 0.0]] * 5)
        result = mapping.map_positions(positions)
        np.testing.assert_array_almost_equal(result, 0.0)

    def test_with_max_radius(self) -> None:
        mapping = RadialMapping(center=(0.0, 0.0, 0.0), max_radius=10.0)
        positions = np.array([[5.0, 0.0, 0.0]])
        result = mapping.map_positions(positions)
        np.testing.assert_almost_equal(result[0], 0.5)
