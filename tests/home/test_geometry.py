from __future__ import annotations

import numpy as np

from dj_ledfx.home.geometry import point_in_polygon, points_in_polygon, polygon_area

SQUARE = ((0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0))
L_SHAPE = ((0.0, 0.0), (4.0, 0.0), (4.0, 2.0), (2.0, 2.0), (2.0, 4.0), (0.0, 4.0))


def test_points_in_a_square() -> None:
    points = np.array([[1.0, 1.0], [5.0, 1.0], [2.0, -0.5], [3.9, 3.9]])
    assert points_in_polygon(points, SQUARE).tolist() == [True, False, False, True]


def test_points_in_a_concave_room() -> None:
    assert point_in_polygon((1.0, 3.0), L_SHAPE)
    assert point_in_polygon((3.0, 1.0), L_SHAPE)
    assert not point_in_polygon((3.0, 3.0), L_SHAPE)  # the missing corner


def test_no_points_is_no_answers() -> None:
    assert points_in_polygon(np.zeros((0, 2)), SQUARE).tolist() == []


def test_polygon_area_either_way_round() -> None:
    assert polygon_area(SQUARE) == 16.0
    assert polygon_area(tuple(reversed(SQUARE))) == 16.0
    assert polygon_area(L_SHAPE) == 12.0
