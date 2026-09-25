from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from dj_ledfx.home.model import HomeError
from dj_ledfx.home.shapes import (
    BentLineShape,
    CylinderShape,
    GridShape,
    LightShape,
    LineShape,
    PointShape,
    ShapeError,
    check_led_order,
    led_positions,
    shape_centre,
    shape_from_dict,
    shape_to_dict,
)
from dj_ledfx.spatial.geometry import DeviceGeometry, MatrixGeometry, TileLayout

SHAPES: list[LightShape] = [
    PointShape((1.0, 2.0, 0.5)),
    LineShape(((0.0, 0.0, 1.0), (1.0, 0.0, 1.0))),
    BentLineShape(((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0))),
    CylinderShape((1.0, 1.0, 0.5), 0.4, 0.05),
    GridShape((1.0, 1.0, 0.8), 0.8, 0.2, (90.0, 0.0, 0.0)),
]


def _tile(width: int, height: int) -> MatrixGeometry:
    return MatrixGeometry(tiles=(TileLayout(0.0, 0.0, width, height),))


@pytest.mark.parametrize("shape", SHAPES, ids=lambda shape: shape.kind)
def test_shapes_read_and_write_in_the_contract_shape(shape: LightShape) -> None:
    data = shape_to_dict(shape)
    assert data["kind"] == shape.kind
    assert shape_from_dict(data) == shape


def test_a_grid_without_a_rotation_lies_flat() -> None:
    grid = shape_from_dict({"kind": "grid", "center": [1, 1, 0.8], "width": 0.9, "depth": 0.3})
    assert isinstance(grid, GridShape) and grid.rotation == (0.0, 0.0, 0.0)
    assert shape_to_dict(grid)["rotation"] == [0.0, 0.0, 0.0]


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        ({"kind": "blob"}, "Unknown light shape"),
        ({"kind": "line", "path": [[0, 0, 0], [1, 0, 0], [2, 0, 0]]}, "2 points"),
        ({"kind": "bent-line", "path": [[0, 0, 0]]}, "at least 2 points"),
        ({"kind": "cylinder", "base": [0, 0, 0], "height": 0.1, "radius": -1}, "0 or more"),
        ({"kind": "point", "position": [0, float("nan"), 0]}, "finite"),
        ({"kind": "grid", "center": [0, 0, 0], "width": 1}, "finite number"),
        ([1, 2, 3], "must be an object"),
    ],
)
def test_bad_shapes_are_refused_with_the_reason(data: Any, reason: str) -> None:
    with pytest.raises(HomeError, match=reason):
        shape_from_dict(data)


def test_each_kind_has_its_own_led_orders() -> None:
    assert check_led_order("line", None) == "along-path"
    assert check_led_order("bent-line", "reverse-path") == "reverse-path"
    assert check_led_order("cylinder", "") == "bottom-to-top"
    assert check_led_order("grid", "columns") == "columns"
    assert check_led_order("point", "anything") == ""  # one LED order only
    with pytest.raises(ShapeError, match="rows, columns"):
        check_led_order("grid", "along-path")


def test_a_line_spaces_its_leds_evenly_along_its_length() -> None:
    line = LineShape(((0.0, 0.0, 1.0), (1.0, 0.0, 1.0)))
    placed = led_positions(line, 4)
    assert np.allclose(placed.pos[:, 0], [0.125, 0.375, 0.625, 0.875])
    assert np.allclose(placed.pos[:, 1:], [0.0, 1.0])
    assert np.allclose(placed.local_u, [0.0, 1 / 3, 2 / 3, 1.0])
    backwards = led_positions(line, 4, "reverse-path")
    assert np.allclose(backwards.pos[:, 0], [0.875, 0.625, 0.375, 0.125])


def test_a_bent_line_follows_its_corners() -> None:
    bent = BentLineShape(((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)))
    placed = led_positions(bent, 4)
    assert np.allclose(placed.pos, [[0.25, 0, 0], [0.75, 0, 0], [1, 0.25, 0], [1, 0.75, 0]])


def test_a_point_with_several_leds_is_a_short_column_on_its_position() -> None:
    placed = led_positions(PointShape((1.0, 2.0, 1.0)), 3)
    assert np.allclose(placed.pos[:, :2], [1.0, 2.0])
    assert np.allclose(placed.pos[:, 2], [0.97, 1.0, 1.03])
    assert np.allclose(led_positions(PointShape((1.0, 2.0, 1.0)), 1).pos, [[1.0, 2.0, 1.0]])


def test_a_cylinder_without_a_matrix_runs_up_its_axis() -> None:
    cylinder = CylinderShape((1.0, 2.0, 0.5), 0.4, 0.05)
    placed = led_positions(cylinder, 4)
    assert np.allclose(placed.pos[:, :2], [1.0, 2.0])
    assert np.allclose(placed.pos[:, 2], [0.55, 0.65, 0.75, 0.85])
    assert np.allclose(placed.local[:, 2], [0.0, 1 / 3, 2 / 3, 1.0])
    down = led_positions(cylinder, 4, "top-to-bottom")
    assert np.allclose(down.pos[:, 2], [0.85, 0.75, 0.65, 0.55])
    assert np.allclose(down.local[:, 2], [1.0, 2 / 3, 1 / 3, 0.0])


def test_a_matrix_cylinder_wraps_its_columns_around_the_axis() -> None:
    cylinder = CylinderShape((0.0, 0.0, 0.0), 0.6, 0.1)
    placed = led_positions(cylinder, 12, geometry=_tile(4, 3))
    assert np.allclose(np.hypot(placed.pos[:, 0], placed.pos[:, 1]), 0.1)
    assert np.allclose(placed.pos[:4, 2], 0.1) and np.allclose(placed.pos[8:, 2], 0.5)
    assert np.allclose(placed.pos[:2, :2], [[0.1, 0.0], [0.0, 0.1]])  # a quarter turn a column
    assert np.allclose(placed.local[:4, 2], 0.0) and np.allclose(placed.local[8:, 2], 1.0)
    down = led_positions(cylinder, 12, "top-to-bottom", _tile(4, 3))
    assert np.allclose(down.pos[:4, 2], 0.5)


def test_a_grid_fills_its_rectangle_in_rows_or_columns() -> None:
    grid = GridShape((1.0, 1.0, 0.8), 0.8, 0.2)  # 8 LEDs: 6 columns, 2 rows
    placed = led_positions(grid, 8)
    assert np.allclose(placed.pos[0], [1.0 - 0.4 + 0.8 / 12, 0.95, 0.8])
    assert np.allclose(placed.pos[5, 0], 1.0 + 0.4 - 0.8 / 12)
    assert np.allclose(placed.pos[6], [placed.pos[0, 0], 1.05, 0.8])  # the second row
    by_columns = led_positions(grid, 8, "columns")
    assert np.allclose(by_columns.pos[1], [placed.pos[0, 0], 1.05, 0.8])


def test_a_grid_turns_and_tilts_with_its_rotation() -> None:
    turned = led_positions(GridShape((0.0, 0.0, 1.0), 1.0, 0.0, (90.0, 0.0, 0.0)), 2)
    assert np.allclose(turned.pos, [[0.0, -0.25, 1.0], [0.0, 0.25, 1.0]])
    stood_up = led_positions(GridShape((0.0, 0.0, 1.0), 0.0, 1.0, (0.0, 90.0, 0.0)), 2)
    assert np.allclose(stood_up.pos, [[0.0, 0.0, 0.75], [0.0, 0.0, 1.25]])


def test_shape_centres() -> None:
    assert shape_centre(SHAPES[0]) == (1.0, 2.0, 0.5)
    assert shape_centre(SHAPES[1]) == (0.5, 0.0, 1.0)
    assert shape_centre(SHAPES[3]) == pytest.approx((1.0, 1.0, 0.7))
    assert shape_centre(SHAPES[4]) == (1.0, 1.0, 0.8)


# Review Focus 5: a degenerate placement, or one made for another LED count, still gives
# one finite position per LED in LED order, so no effect ever produces NaN.
@pytest.mark.parametrize(
    ("shape", "count", "geometry"),
    [
        (PointShape((1.0, 1.0, 1.0)), 3, None),
        (LineShape(((1.0, 1.0, 1.0), (1.0, 1.0, 1.0))), 5, None),  # zero length
        (BentLineShape(((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (1.0, 0.0, 0.0))), 4, None),
        (CylinderShape((0.0, 0.0, 0.0), 0.0, 0.0), 6, None),  # flat and thin
        (CylinderShape((0.0, 0.0, 0.0), 0.12, 0.02), 30, _tile(8, 8)),  # the matrix disagrees
        (CylinderShape((0.0, 0.0, 0.0), 0.12, 0.02), 30, _tile(5, 6)),  # it agrees
        (GridShape((0.0, 0.0, 0.0), 0.0, 0.0), 7, None),  # zero size
        (GridShape((0.0, 0.0, 0.0), 0.9, 0.3), 1, None),
        (LineShape(((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))), 1, None),
    ],
)
def test_every_shape_gives_one_finite_position_per_led(
    shape: LightShape, count: int, geometry: DeviceGeometry | None
) -> None:
    placed = led_positions(shape, count, geometry=geometry)
    assert placed.pos.shape == (count, 3) and placed.local.shape == (count, 3)
    for array in (placed.pos, placed.local, placed.local_u):
        assert np.isfinite(array).all()
    assert placed.local.min() >= 0.0 and placed.local.max() <= 1.0
    assert placed.local_u[0] == 0.0 and np.all(np.diff(placed.local_u) > 0)
    assert led_positions(shape, 0).count == 0
