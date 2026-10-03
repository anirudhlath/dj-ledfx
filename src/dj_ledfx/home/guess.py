"""Placement guessing (spec §6.2) and the old scene placements moved onto the map (§6.5,
ruling 12). Every guess is unconfirmed: only the owner confirms a placement.

Scene placements are in the old scene editor's axes, three.js's (x, y up, z towards the
viewer). On the map that is (x, z, y): east, south, up.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Collection, Iterable, Sequence
from typing import Literal

import numpy as np
from loguru import logger
from numpy.typing import NDArray

from dj_ledfx.devices.lights import LightEntry, LightIndex
from dj_ledfx.effects.ledset import LED_PITCH_M
from dj_ledfx.home.geometry import point_in_polygon, polygon_area
from dj_ledfx.home.model import Home, Room, Vec3
from dj_ledfx.home.seed import SeedLight, normalise_name
from dj_ledfx.home.shapes import (
    BentLineShape,
    GridShape,
    LightShape,
    LineShape,
    Placement,
    PointShape,
    check_led_order,
)
from dj_ledfx.home.store import ScenePlacement
from dj_ledfx.spatial.geometry import DeviceGeometry, MatrixGeometry, StripGeometry

SPREAD_RADIUS_M = 0.8
GUESS_HEIGHT_M = 1.0
STANDING = (0.0, 90.0, 0.0)  # a grid tilted up to face south, as the scene hung matrices
UPRIGHT_BASE_M = 0.1  # an upright lamp's LEDs start this far off the floor
UPRIGHT_RISE = 0.9  # a strip that rises more than this per metre along it is an upright lamp
# A grid stood up with its first row at the top, as a matrix's own frame has it.
UPRIGHT_GRID = (0.0, -90.0, 0.0)


def seed_matches(lights: Iterable[LightEntry], seeds: Sequence[SeedLight]) -> dict[str, SeedLight]:
    """Light id -> the seed light of the same name. Each seed goes to the first light
    that matches it."""
    by_name: dict[str, list[SeedLight]] = {}
    for seed in seeds:
        by_name.setdefault(normalise_name(seed.name), []).append(seed)
    matches: dict[str, SeedLight] = {}
    for light in lights:
        options = by_name.get(normalise_name(light.name))
        if options:
            matches[light.id] = options.pop(0)
    return matches


def largest_room(home: Home) -> Room:
    return max(home.rooms, key=lambda room: polygon_area(room.polygon))


def _spread(home: Home, count: int) -> list[Vec3]:
    room = largest_room(home)
    cx, cy = room.label_at
    points: list[Vec3] = []
    for step in range(count):
        angle = 2.0 * math.pi * step / max(count, 1)
        x, y = cx + SPREAD_RADIUS_M * math.cos(angle), cy + SPREAD_RADIUS_M * math.sin(angle)
        if not point_in_polygon((x, y), room.polygon):
            x, y = cx, cy
        points.append((x, y, GUESS_HEIGHT_M))
    return points


def _no_form(light: LightEntry) -> DeviceGeometry | None:
    return None


def guess_placements(
    home: Home,
    lights: Sequence[LightEntry],
    placed: Collection[str],
    seeds: Sequence[SeedLight],
    geometry_of: Callable[[LightEntry], DeviceGeometry | None] = _no_form,
) -> dict[str, Placement]:
    """A guess for each light not in `placed`: its seed's placement, or a spot round the
    largest room, in the light's form there (geometry_of gives a light's geometry)."""
    matches = seed_matches(lights, seeds)
    guesses: dict[str, Placement] = {}
    loose: list[LightEntry] = []
    for light in lights:
        if light.id in placed:
            continue
        seed = matches.get(light.id)
        if seed is not None:
            guesses[light.id] = seed.placement
        else:
            loose.append(light)
    for light, point in zip(loose, _spread(home, len(loose)), strict=True):
        guesses[light.id] = placed_in_form(point, light.leds, geometry_of(light))
    return guesses


def _to_map(vector: Sequence[float] | NDArray[np.float64]) -> NDArray[np.float64]:
    x, y, z = (float(value) for value in vector)
    return np.array([x, z, y])


def _vec(values: NDArray[np.float64]) -> Vec3:
    return (float(values[0]), float(values[1]), float(values[2]))


def _rise(geometry: StripGeometry) -> float:
    """How far up the map a strip runs per metre along it: near ±1 for an upright lamp. The
    direction is a unit vector, and its scene y is the map's up (see `_to_map`)."""
    return geometry.direction[1]


def _matrix_size(geometry: MatrixGeometry) -> tuple[float, float]:
    """The width and height the matrix's tiles cover, in metres."""
    pitch = geometry.pixel_pitch
    left = min(tile.offset_x for tile in geometry.tiles)
    right = max(tile.offset_x + tile.width * pitch for tile in geometry.tiles)
    top = min(tile.offset_y for tile in geometry.tiles)
    bottom = max(tile.offset_y + tile.height * pitch for tile in geometry.tiles)
    return right - left, bottom - top


Form = Literal["point", "upright", "line", "grid"]


def _form(leds: int, geometry: DeviceGeometry | None) -> Form:
    """The form a light shows on the map (the light-output plan's ruling 19): a strip that
    runs near vertical is an upright lamp, any other strip a line, and a matrix a grid of
    its tiles. A light of one LED, of no known form, or a matrix with no tiles is a point.
    `placed_in_form` and `in_form` both go by it, so a placement made in form stays in it."""
    if leds <= 1:
        return "point"
    if isinstance(geometry, StripGeometry):
        return "upright" if abs(_rise(geometry)) > UPRIGHT_RISE else "line"
    if isinstance(geometry, MatrixGeometry) and geometry.tiles:
        return "grid"
    return "point"


def placed_in_form(at: Vec3, leds: int, geometry: DeviceGeometry | None) -> Placement:
    """An unconfirmed placement at `at` that shows the light's form. An upright lamp stands
    on the floor below `at`, a vertical line as long as its geometry; a strip lies through
    `at` along its direction; a matrix stands at `at` as a grid of its tiles' size, first
    row at the top (a chain of tiles is one grid, in rows); a point is at `at`."""
    form = _form(leds, geometry)
    if form == "upright" and isinstance(geometry, StripGeometry):
        x, y, _ = at
        path = ((x, y, UPRIGHT_BASE_M), (x, y, UPRIGHT_BASE_M + geometry.length))
        order = "along-path" if _rise(geometry) > 0 else "reverse-path"
        return Placement(LineShape(path), order)
    if form == "line" and isinstance(geometry, StripGeometry):
        half = _to_map(geometry.direction) * geometry.length / 2.0
        centre = np.asarray(at, dtype=np.float64)
        return Placement(LineShape((_vec(centre - half), _vec(centre + half))), "along-path")
    if form == "grid" and isinstance(geometry, MatrixGeometry):
        width, height = _matrix_size(geometry)
        return Placement(GridShape(at, width, height, UPRIGHT_GRID), "rows")
    return Placement(PointShape(at), check_led_order("point", None))


def in_form(shape: LightShape, leds: int, geometry: DeviceGeometry | None) -> bool:
    """Whether a placement shows the light's form (see `_form`). Two things hide it: a
    point for a light that has a form, and an upright lamp lying down."""
    form = _form(leds, geometry)
    if form == "point":
        return True
    if isinstance(shape, PointShape):
        return False
    return form != "upright" or _stands(shape)


def _stands(shape: LightShape) -> bool:
    """Whether a line rises at least as far as it spreads. Other shapes aren't judged."""
    if not isinstance(shape, LineShape | BentLineShape):
        return True
    path = np.asarray(shape.path, dtype=np.float64)
    height = float(path[:, 2].max() - path[:, 2].min())
    spread = float(np.linalg.norm(path[:, :2].max(axis=0) - path[:, :2].min(axis=0)))
    return height >= spread


def _scene_shape(placement: ScenePlacement, at: NDArray[np.float64]) -> LightShape:
    if placement.geometry == "strip" and placement.direction is not None and placement.length:
        direction = _to_map(placement.direction)
        norm = float(np.linalg.norm(direction))
        if norm > 1e-9:
            return LineShape((_vec(at), _vec(at + direction / norm * placement.length)))
    if placement.geometry == "matrix":
        columns, rows = max(placement.cols or 1, 1), max(placement.rows or 1, 1)
        return GridShape(_vec(at), columns * LED_PITCH_M, rows * LED_PITCH_M, STANDING)
    return PointShape(_vec(at))


def moved_scene_placements(
    home: Home,
    scene: Sequence[ScenePlacement],
    room_of: Callable[[str], str | None],
) -> dict[str, Placement]:
    """Device id -> its old scene placement on the map: offset from its room's label point
    by its position relative to its scene's centre, at guess height. The first scene that
    placed a device wins; a device with no known room goes to the largest room. A placement
    that can't be moved (a coordinate that isn't finite, a shape the map refuses) is logged
    and skipped, and its light is guessed like any unplaced one: a bad old scene never
    stops the app (spec §8)."""
    first: dict[str, ScenePlacement] = {}
    for placement in scene:
        first.setdefault(placement.device_id, placement)
    by_scene: dict[str, list[ScenePlacement]] = {}
    for placement in first.values():
        if not all(math.isfinite(value) for value in placement.position):
            _skipped(placement, "its position isn't finite")
            continue
        by_scene.setdefault(placement.scene_id, []).append(placement)
    fallback = largest_room(home)
    moved: dict[str, Placement] = {}
    for members in by_scene.values():
        centre = np.mean(np.asarray([member.position for member in members]), axis=0)
        for member in members:
            room = home.room(room_of(member.device_id) or "") or fallback
            offset = _to_map(np.asarray(member.position) - centre)
            height = min(max(GUESS_HEIGHT_M + offset[2], 0.0), home.ceiling)
            at = np.array([room.label_at[0] + offset[0], room.label_at[1] + offset[1], height])
            try:
                shape = _scene_shape(member, at)
            except ValueError as exc:  # a ShapeError too
                _skipped(member, str(exc))
                continue
            moved[member.device_id] = Placement(shape, check_led_order(shape.kind, None))
    return moved


def _skipped(placement: ScenePlacement, reason: str) -> None:
    logger.warning(
        "Light {}: its old scene placement can't be moved onto the map ({}); guessing instead",
        placement.device_id,
        reason,
    )


def first_placements(
    home: Home,
    lights: Sequence[LightEntry],
    seeds: Sequence[SeedLight],
    scene: Sequence[ScenePlacement],
) -> dict[str, Placement]:
    """The placements M2 starts with, by target id: each light's seed, the old scene
    placements over them (a PC part's scene placement places that part on its own), and
    a spread guess for every light still unplaced. Devices no longer known are skipped."""
    matches = seed_matches(lights, seeds)
    placements: dict[str, Placement] = {
        light_id: seed.placement for light_id, seed in matches.items()
    }
    index = LightIndex(lights)

    def room_of(device_id: str) -> str | None:
        seed = matches.get(index.light_of(device_id))
        return seed.room if seed is not None else None

    known = [p for p in scene if index.get(index.light_of(p.device_id)) is not None]
    placements.update(moved_scene_placements(home, known, room_of))
    placements.update(guess_placements(home, lights, set(placements), ()))
    return placements
