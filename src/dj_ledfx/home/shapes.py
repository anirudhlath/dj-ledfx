"""Where a light sits on the home map (engine spec §6.1; web spec §12.2's LightShape),
and one position per LED from that.

Shapes are in metres on the map's axes (x east, y south, z up). Only a grid turns (ruling
6): its rotation is (turn, tilt, roll) in degrees, and a grid lying flat is rolled about
y, tilted about x, then turned about z. The LED order says where LED 1 is and which way
the rest run. home.json uses each kind's default order, the first in LED_ORDERS.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, ClassVar, cast

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.ledset import LED_PITCH_M, PlacedLeds, steps_along
from dj_ledfx.home.model import HomeError, Vec3, finite, non_negative, vec3
from dj_ledfx.spatial.geometry import DeviceGeometry, MatrixGeometry
from dj_ledfx.timing import as_utc

KINDS = ("point", "line", "bent-line", "cylinder", "grid")
LED_ORDERS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "point": ("",),
        "line": ("along-path", "reverse-path"),
        "bent-line": ("along-path", "reverse-path"),
        "cylinder": ("bottom-to-top", "top-to-bottom"),
        "grid": ("rows", "columns"),
    }
)


# No coordinate or size goes past this, in metres: far beyond any home, and small enough
# that the LED sets' sums and norms never overflow (a 1e308 m point made a zone's frames NaN).
MAX_METRES = 1000.0


class ShapeError(HomeError):
    """A light shape or LED order that can't be used, with the reason."""


# A shape checks itself when it's made, however it's made: read from the contract's form
# or built in code (the old scene placements). vec3 and non_negative are the map's checks.


def _check_point(point: Vec3, what: str) -> None:
    if any(abs(value) > MAX_METRES for value in vec3(point, what)):
        raise ShapeError(f"{what} must be within {MAX_METRES:g} m of the plan's origin")


def _check_size(value: float, what: str) -> None:
    if non_negative(value, what) > MAX_METRES:
        raise ShapeError(f"{what} must be {MAX_METRES:g} m or less")


@dataclass(frozen=True, slots=True)
class PointShape:
    kind: ClassVar[str] = "point"
    position: Vec3

    def __post_init__(self) -> None:
        _check_point(self.position, "A point's position")


@dataclass(frozen=True, slots=True)
class LineShape:
    kind: ClassVar[str] = "line"
    path: tuple[Vec3, Vec3]

    def __post_init__(self) -> None:
        if len(self.path) != 2:
            raise ShapeError("A line's path must be 2 points")
        for point in self.path:
            _check_point(point, "A line's path")


@dataclass(frozen=True, slots=True)
class BentLineShape:
    kind: ClassVar[str] = "bent-line"
    path: tuple[Vec3, ...]

    def __post_init__(self) -> None:
        if len(self.path) < 2:
            raise ShapeError("A bent line's path needs at least 2 points")
        for point in self.path:
            _check_point(point, "A bent line's path")


@dataclass(frozen=True, slots=True)
class CylinderShape:
    kind: ClassVar[str] = "cylinder"
    base: Vec3
    height: float
    radius: float

    def __post_init__(self) -> None:
        _check_point(self.base, "A cylinder's base")
        _check_size(self.height, "A cylinder's height")
        _check_size(self.radius, "A cylinder's radius")


@dataclass(frozen=True, slots=True)
class GridShape:
    kind: ClassVar[str] = "grid"
    center: Vec3
    width: float
    depth: float
    rotation: Vec3 = (0.0, 0.0, 0.0)  # turn, tilt, roll in degrees

    def __post_init__(self) -> None:
        _check_point(self.center, "A grid's centre")
        _check_size(self.width, "A grid's width")
        _check_size(self.depth, "A grid's depth")
        vec3(self.rotation, "A grid's rotation")


LightShape = PointShape | LineShape | BentLineShape | CylinderShape | GridShape


@dataclass(frozen=True, slots=True)
class Placement:
    """A light's (or a PC part's) place on the map. Moving it doesn't confirm it."""

    shape: LightShape
    led_order: str
    confirmed: bool = False
    confirmed_at: datetime | None = None


def check_led_order(kind: str, order: str | None) -> str:
    """The order to store: the kind's default for none, and "" for a point, whose LEDs
    have no order to choose."""
    options = LED_ORDERS[kind]
    if kind == "point" or not order:
        return options[0]
    if order not in options:
        raise ShapeError(f"A {kind}'s LED order must be one of {', '.join(options)}")
    return order


# --- the contract's form ---------------------------------------------------------------


def _path(value: Any, what: str) -> tuple[Vec3, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ShapeError(f"{what} must be a list of points")
    return tuple(vec3(point, what) for point in value)


def shape_from_dict(data: Mapping[str, Any]) -> LightShape:
    """A shape in web spec §12.2's form. Raises HomeError, naming the field, when it can't."""
    if not isinstance(data, Mapping):
        raise ShapeError("A light shape must be an object")
    kind = data.get("kind")
    if kind == "point":
        return PointShape(vec3(data.get("position"), "A point's position"))
    if kind == "line":
        return LineShape(cast(tuple[Vec3, Vec3], _path(data.get("path"), "A line's path")))
    if kind == "bent-line":
        return BentLineShape(_path(data.get("path"), "A bent line's path"))
    if kind == "cylinder":
        return CylinderShape(
            vec3(data.get("base"), "A cylinder's base"),
            finite(data.get("height"), "A cylinder's height"),
            finite(data.get("radius"), "A cylinder's radius"),
        )
    if kind == "grid":
        rotation = data.get("rotation")
        return GridShape(
            vec3(data.get("center"), "A grid's centre"),
            finite(data.get("width"), "A grid's width"),
            finite(data.get("depth"), "A grid's depth"),
            vec3(rotation, "A grid's rotation") if rotation is not None else (0.0, 0.0, 0.0),
        )
    raise ShapeError(f"Unknown light shape {kind!r}; expected one of {', '.join(KINDS)}")


def shape_to_dict(shape: LightShape) -> dict[str, Any]:
    if isinstance(shape, PointShape):
        return {"kind": shape.kind, "position": list(shape.position)}
    if isinstance(shape, LineShape | BentLineShape):
        return {"kind": shape.kind, "path": [list(point) for point in shape.path]}
    if isinstance(shape, CylinderShape):
        return {
            "kind": shape.kind,
            "base": list(shape.base),
            "height": shape.height,
            "radius": shape.radius,
        }
    return {
        "kind": shape.kind,
        "center": list(shape.center),
        "width": shape.width,
        "depth": shape.depth,
        "rotation": list(shape.rotation),
    }


def placement_to_dict(placement: Placement) -> dict[str, Any]:
    """A placement in the contract's fields (snake_case): the shape as shape_to_dict
    gives it, and confirmed_at as a datetime or None."""
    return {
        "shape": shape_to_dict(placement.shape),
        "led_order": placement.led_order,
        "confirmed": placement.confirmed,
        "confirmed_at": placement.confirmed_at,
    }


def placement_from_dict(data: Mapping[str, Any]) -> Placement:
    """A stored placement, checked as a new one is: the kind's default LED order when it
    has none, confirmed only when confirmed is true, and confirmed_at a datetime or ISO
    text. Raises ValueError (a ShapeError, when it's the shape)."""
    raw = data.get("shape")
    if not isinstance(raw, Mapping):
        raise ShapeError("A placement needs a shape")
    shape = shape_from_dict(raw)
    order = data.get("led_order")
    at = data.get("confirmed_at")
    if isinstance(at, str) and at:
        at = datetime.fromisoformat(at)
    return Placement(
        shape,
        check_led_order(shape.kind, order if isinstance(order, str) else None),
        data.get("confirmed") is True,
        as_utc(at) if isinstance(at, datetime) else None,
    )


def shape_centre(shape: LightShape) -> Vec3:
    """The middle of the shape: what decides its room, and where a PC part's slice sits."""
    if isinstance(shape, PointShape):
        return shape.position
    if isinstance(shape, LineShape | BentLineShape):
        x, y, z = np.mean(np.asarray(shape.path, dtype=np.float64), axis=0)
        return (float(x), float(y), float(z))
    if isinstance(shape, CylinderShape):
        x, y, z = shape.base
        return (x, y, z + shape.height / 2.0)
    return shape.center


# --- one position per LED --------------------------------------------------------------


def led_positions(
    shape: LightShape, count: int, led_order: str = "", geometry: DeviceGeometry | None = None
) -> PlacedLeds:
    """Each of `count` LEDs' position, in LED order. Whatever the shape, every LED gets a
    finite position; a degenerate shape stacks them."""
    if count <= 0:
        return PlacedLeds.from_positions(np.zeros((0, 3)))
    order = check_led_order(shape.kind, led_order)
    if isinstance(shape, PointShape):
        return _point(shape, count)
    if isinstance(shape, LineShape | BentLineShape):
        return PlacedLeds.from_positions(_along_path(shape.path, count, order == "reverse-path"))
    if isinstance(shape, CylinderShape):
        return _cylinder(shape, count, order == "top-to-bottom", geometry)
    return _grid(shape, count, order == "columns")


def _spread(count: int) -> NDArray[np.float64]:
    """0..1 across `count` steps; a single step sits in the middle (LedSet.local's)."""
    return np.arange(count) / (count - 1) if count > 1 else np.full(1, 0.5)


def _point(shape: PointShape, count: int) -> PlacedLeds:
    x, y, z = shape.position
    offsets = (np.arange(count) - (count - 1) / 2.0) * LED_PITCH_M
    column = np.column_stack([np.full(count, x), np.full(count, y), z + offsets])
    return PlacedLeds.from_positions(column)


def _along_path(path: Sequence[Vec3], count: int, reverse: bool) -> NDArray[np.float64]:
    points = np.asarray(path, dtype=np.float64)
    if reverse:
        points = points[::-1]
    lengths = np.linalg.norm(np.diff(points, axis=0), axis=1)
    total = float(lengths.sum())
    if total <= 1e-9:
        return np.repeat(points[:1], count, axis=0)
    starts = np.concatenate([[0.0], np.cumsum(lengths)])
    at = (np.arange(count) + 0.5) / count * total
    segment = np.clip(np.searchsorted(starts, at, side="right") - 1, 0, len(lengths) - 1)
    safe = np.maximum(lengths[segment], 1e-12)
    fraction = np.clip((at - starts[segment]) / safe, 0.0, 1.0)
    spaced: NDArray[np.float64] = (
        points[segment] + (points[segment + 1] - points[segment]) * fraction[:, None]
    )
    return spaced


def _single_tile(geometry: DeviceGeometry | None, count: int) -> tuple[int, int] | None:
    if not isinstance(geometry, MatrixGeometry) or len(geometry.tiles) != 1:
        return None
    tile = geometry.tiles[0]
    return (tile.width, tile.height) if tile.width * tile.height == count else None


def _cylinder(
    shape: CylinderShape, count: int, top_down: bool, geometry: DeviceGeometry | None
) -> PlacedLeds:
    x, y, z = shape.base
    tile = _single_tile(geometry, count)
    if tile is None:  # a strip up the axis
        up = (np.arange(count) + 0.5) / count
        local_z = steps_along(count)
        if top_down:
            up, local_z = up[::-1], local_z[::-1]
        pos = np.column_stack([np.full(count, x), np.full(count, y), z + up * shape.height])
        local = np.column_stack([np.full(count, 0.5), np.full(count, 0.5), local_z])
        if count == 1:
            local[:, 2] = 0.5
        return PlacedLeds(pos, local, steps_along(count))
    columns, rows = tile
    index = np.arange(count)
    row, column = index // columns, index % columns
    up = (row + 0.5) / rows
    local_z = _spread(rows)[row]
    if top_down:
        up, local_z = 1.0 - up, 1.0 - local_z
    angle = 2.0 * math.pi * column / columns
    pos = np.column_stack(
        [
            x + shape.radius * np.cos(angle),
            y + shape.radius * np.sin(angle),
            z + up * shape.height,
        ]
    )
    local = np.column_stack([_spread(columns)[column], np.full(count, 0.5), local_z])
    return PlacedLeds(pos, local, steps_along(count))


def _columns(count: int, width: float, depth: float) -> int:
    if width <= 1e-9 and depth <= 1e-9:
        return max(1, math.ceil(math.sqrt(count)))
    if depth <= 1e-9:
        return count
    if width <= 1e-9:
        return 1
    return max(1, min(count, math.ceil(math.sqrt(count * width / depth))))


def _rotation(rotation: Vec3) -> NDArray[np.float64]:
    turn, tilt, roll = (math.radians(angle) for angle in rotation)
    about_z = np.array(
        [[math.cos(turn), -math.sin(turn), 0.0], [math.sin(turn), math.cos(turn), 0.0], [0, 0, 1]]
    )
    about_x = np.array(
        [[1, 0, 0], [0.0, math.cos(tilt), -math.sin(tilt)], [0.0, math.sin(tilt), math.cos(tilt)]]
    )
    about_y = np.array(
        [[math.cos(roll), 0.0, math.sin(roll)], [0, 1, 0], [-math.sin(roll), 0.0, math.cos(roll)]]
    )
    matrix: NDArray[np.float64] = about_z @ about_x @ about_y
    return matrix


def _grid(shape: GridShape, count: int, by_columns: bool) -> PlacedLeds:
    columns = _columns(count, shape.width, shape.depth)
    rows = math.ceil(count / columns)
    index = np.arange(count)
    if by_columns:
        column, row = index // rows, index % rows
    else:
        row, column = index // columns, index % columns
    flat = np.column_stack(
        [
            ((column + 0.5) / columns - 0.5) * shape.width,
            ((row + 0.5) / rows - 0.5) * shape.depth,
            np.zeros(count),
        ]
    )
    pos = np.asarray(shape.center, dtype=np.float64) + flat @ _rotation(shape.rotation).T
    # As M1 hung a matrix: row 0 at the top of the light's own frame.
    local = np.column_stack(
        [_spread(columns)[column], np.full(count, 0.5), 1.0 - _spread(rows)[row]]
    )
    return PlacedLeds(pos, local, steps_along(count))
