"""Placement guessing (spec §6.2) and the old scene placements moved onto the map (§6.5,
ruling 12). Every guess is unconfirmed: only the owner confirms a placement.

Scene placements are in the old scene editor's axes, three.js's (x, y up, z towards the
viewer). On the map that is (x, z, y): east, south, up.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import replace

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.devices.lights import LightEntry
from dj_ledfx.effects.ledset import LED_PITCH_M
from dj_ledfx.home.geometry import point_in_polygon, polygon_area
from dj_ledfx.home.model import Home, Room, Vec3
from dj_ledfx.home.seed import SeedLight, normalise_name
from dj_ledfx.home.shapes import (
    GridShape,
    LightShape,
    LineShape,
    Placement,
    PointShape,
    check_led_order,
)
from dj_ledfx.home.store import ScenePlacement

SPREAD_RADIUS_M = 0.8
GUESS_HEIGHT_M = 1.0
STANDING = (0.0, 90.0, 0.0)  # a grid tilted up to face south, as the scene hung matrices


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


def guess_placements(
    home: Home,
    lights: Sequence[LightEntry],
    placed: Collection[str],
    seeds: Sequence[SeedLight],
) -> dict[str, Placement]:
    """A guess for each light not in `placed`: its seed's placement, or a point spread
    round the largest room."""
    matches = seed_matches(lights, seeds)
    guesses: dict[str, Placement] = {}
    loose: list[str] = []
    for light in lights:
        if light.id in placed:
            continue
        seed = matches.get(light.id)
        if seed is not None:
            guesses[light.id] = replace(seed.placement, confirmed=False, confirmed_at=None)
        else:
            loose.append(light.id)
    for light_id, point in zip(loose, _spread(home, len(loose)), strict=True):
        guesses[light_id] = Placement(PointShape(point), check_led_order("point", None))
    return guesses


def _to_map(vector: Sequence[float] | NDArray[np.float64]) -> NDArray[np.float64]:
    x, y, z = (float(value) for value in vector)
    return np.array([x, z, y])


def _vec(values: NDArray[np.float64]) -> Vec3:
    return (float(values[0]), float(values[1]), float(values[2]))


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
    placed a device wins; a device with no known room goes to the largest room."""
    first: dict[str, ScenePlacement] = {}
    for placement in scene:
        first.setdefault(placement.device_id, placement)
    by_scene: dict[str, list[ScenePlacement]] = {}
    for placement in first.values():
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
            shape = _scene_shape(member, at)
            moved[member.device_id] = Placement(shape, check_led_order(shape.kind, None))
    return moved


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
        light_id: replace(seed.placement, confirmed=False, confirmed_at=None)
        for light_id, seed in matches.items()
    }
    light_of: Mapping[str, str] = {
        device: entry.id for entry in lights for device in entry.devices
    }

    def room_of(device_id: str) -> str | None:
        seed = matches.get(light_of.get(device_id, device_id))
        return seed.room if seed is not None else None

    known = [placement for placement in scene if placement.device_id in light_of]
    placements.update(moved_scene_placements(home, known, room_of))
    placements.update(guess_placements(home, lights, set(placements), ()))
    return placements
