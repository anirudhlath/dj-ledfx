"""Plane geometry on the home map's floor plan (x east, y south)."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

Polygon = Sequence[tuple[float, float]]


def points_in_polygon(points: NDArray[np.float64], polygon: Polygon) -> NDArray[np.bool_]:
    """Which of the (N, 2) points lie inside the polygon, by the even-odd rule. A point
    exactly on an edge may land on either side."""
    xs, ys = points[:, 0], points[:, 1]
    inside = np.zeros(len(points), dtype=bool)
    count = len(polygon)
    for index in range(count):
        x1, y1 = polygon[index]
        x2, y2 = polygon[(index + 1) % count]
        crosses = (y1 > ys) != (y2 > ys)  # never true for a flat edge, so y2 != y1 below
        if not crosses.any():
            continue
        x_at = x1 + (ys - y1) * (x2 - x1) / (y2 - y1)
        inside ^= crosses & (xs < x_at)
    return inside


def point_in_polygon(point: tuple[float, float], polygon: Polygon) -> bool:
    """points_in_polygon for one point, in plain Python: numpy costs more than it saves
    on a single point, and the map asks this for every light."""
    x, y = point
    inside = False
    x1, y1 = polygon[-1]
    for x2, y2 in polygon:
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
        x1, y1 = x2, y2
    return inside


def polygon_area(polygon: Polygon) -> float:
    """The polygon's area in square metres (the shoelace formula), whichever way it winds."""
    xs = np.array([point[0] for point in polygon], dtype=np.float64)
    ys = np.array([point[1] for point in polygon], dtype=np.float64)
    return float(abs(np.dot(xs, np.roll(ys, -1)) - np.dot(ys, np.roll(xs, -1))) / 2.0)
