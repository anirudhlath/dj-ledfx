from __future__ import annotations

import numpy as np

from dj_ledfx.effects.ledset import DEVICE_GAP_M, LedSource, build_ledset
from dj_ledfx.spatial.geometry import MatrixGeometry, PointGeometry, StripGeometry, TileLayout


def test_slices_follow_source_order() -> None:
    leds = build_ledset([LedSource("a", 3), LedSource("b", 5), LedSource("c", 1)])
    assert leds.count == 9
    assert [(s.device_id, s.start, s.stop) for s in leds.slices] == [
        ("a", 0, 3),
        ("b", 3, 8),
        ("c", 8, 9),
    ]
    assert leds.device.tolist() == [0, 0, 0, 1, 1, 1, 1, 1, 2]
    assert leds.slice_for("b") is not None and leds.slice_for("b").count == 5
    assert leds.slice_for("missing") is None


def test_arrays_have_the_documented_shapes_and_types() -> None:
    leds = build_ledset([LedSource("a", 4), LedSource("b", 2)])
    for name in ("pos", "npos", "local"):
        array = getattr(leds, name)
        assert array.shape == (6, 3), name
        assert array.dtype == np.float32, name
    assert leds.local_u.shape == (6,) and leds.local_u.dtype == np.float32
    assert leds.room.dtype == np.int32 and leds.room.tolist() == [0] * 6
    assert leds.device.dtype == np.int32
    assert dict(leds.anchors) == {}


def test_device_without_geometry_is_a_vertical_strip() -> None:
    leds = build_ledset([LedSource("a", 5)])
    assert np.allclose(leds.local_u, [0.0, 0.25, 0.5, 0.75, 1.0])
    assert np.allclose(leds.local[:, 2], [0.0, 0.25, 0.5, 0.75, 1.0])
    assert np.allclose(leds.local[:, 0], 0.5)  # degenerate axis
    assert np.allclose(np.diff(leds.pos[:, 2]), 0.03)


def test_matrix_rows_run_down_from_the_top() -> None:
    matrix = MatrixGeometry(tiles=(TileLayout(0.0, 0.0, 2, 2),))
    leds = build_ledset([LedSource("tile", 4, matrix)])
    # LED order is row-major with row 0 at the top.
    assert np.allclose(leds.local[:, 0], [0.0, 1.0, 0.0, 1.0])
    assert np.allclose(leds.local[:, 2], [1.0, 1.0, 0.0, 0.0])


def test_matrix_with_the_wrong_pixel_count_falls_back_to_a_strip() -> None:
    matrix = MatrixGeometry(tiles=(TileLayout(0.0, 0.0, 8, 8),))
    leds = build_ledset([LedSource("tile", 5, matrix)])
    assert np.allclose(leds.local[:, 2], [0.0, 0.25, 0.5, 0.75, 1.0])


def test_strip_geometry_is_followed() -> None:
    strip = StripGeometry(direction=(1.0, 0.0, 0.0), length=1.0)
    leds = build_ledset([LedSource("strip", 4, strip)])
    assert np.all(np.diff(leds.pos[:, 0]) > 0)
    assert np.allclose(leds.pos[:, 2], 0.0)


def test_point_with_several_leds_falls_back_to_a_strip() -> None:
    leds = build_ledset([LedSource("lamp", 3, PointGeometry())])
    assert np.allclose(leds.local[:, 2], [0.0, 0.5, 1.0])


def test_devices_sit_side_by_side_with_a_gap() -> None:
    strip = StripGeometry(direction=(1.0, 0.0, 0.0), length=1.0)
    leds = build_ledset([LedSource("a", 4, strip), LedSource("b", 4, strip)])
    a = leds.pos[leds.device == 0]
    b = leds.pos[leds.device == 1]
    assert b[:, 0].min() - a[:, 0].max() == np.float32(DEVICE_GAP_M)


def test_normalised_positions_span_the_zone() -> None:
    leds = build_ledset([LedSource("a", 3), LedSource("b", 3)])
    assert leds.npos.min() >= 0.0 and leds.npos.max() <= 1.0
    assert np.isclose(leds.npos[:, 0].min(), 0.0) and np.isclose(leds.npos[:, 0].max(), 1.0)
    assert np.allclose(leds.npos[:, 1], 0.5)  # every LED at y = 0


def test_single_led_device() -> None:
    leds = build_ledset([LedSource("bulb", 1)])
    assert leds.count == 1
    assert leds.local_u.tolist() == [0.0]
    assert np.allclose(leds.local, 0.5)


def test_empty_zone_has_no_leds() -> None:
    leds = build_ledset([])
    assert leds.count == 0
    assert leds.pos.shape == (0, 3)
    assert leds.slices == ()
