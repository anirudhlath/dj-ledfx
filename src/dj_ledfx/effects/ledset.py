"""A zone's LEDs in one fixed order, with positions (spec §5.1).

Each light's LEDs sit where the home map puts them: home/shapes.py turns a placement into
PlacedLeds. A light the map doesn't place yet (or whose placement is for another LED
count) is laid out as M1 did, in its own geometry beside the other unplaced lights, and
that group is moved to the placed lights' mean, or to the home's centre when nothing is
placed, so an effect never sees it at the origin. The set also carries the zone's Space:
the anchors, rooms and ceiling its effects can ask about.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from functools import cached_property
from types import MappingProxyType

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.spatial.geometry import (
    DeviceGeometry,
    MatrixGeometry,
    StripGeometry,
    expand_positions,
)

LED_PITCH_M = 0.03
DEVICE_GAP_M = 0.5
NO_ROOM = -1

Vec3 = tuple[float, float, float]


def _no_points() -> Mapping[str, NDArray[np.float32]]:
    return MappingProxyType({})


def _same_points(
    one: Mapping[str, NDArray[np.float32]], other: Mapping[str, NDArray[np.float32]]
) -> bool:
    return one.keys() == other.keys() and all(np.array_equal(one[k], other[k]) for k in one)


@dataclass(frozen=True, slots=True)
class DeviceSlice:
    device_id: str
    start: int
    stop: int

    @property
    def count(self) -> int:
        return self.stop - self.start


@dataclass(frozen=True, eq=False, slots=True)
class PlacedLeds:
    """One light's LEDs where the home map puts them, in LED order."""

    pos: NDArray[np.float64]  # (n, 3) metres on the map
    local: NDArray[np.float64]  # (n, 3) 0..1 within the light's own shape, z up
    local_u: NDArray[np.float64]  # (n,) 0..1 along the LED order

    @property
    def count(self) -> int:
        return int(self.pos.shape[0])

    @classmethod
    def from_positions(cls, pos: NDArray[np.float64]) -> PlacedLeds:
        """LEDs at these positions, their local positions taken from their own bounds."""
        points = np.asarray(pos, dtype=np.float64).reshape(-1, 3)
        if len(points) == 0:
            return cls(points, np.zeros((0, 3)), np.zeros(0))
        local = _normalise(points, points.min(axis=0), points.max(axis=0))
        return cls(points, local, steps_along(len(points)))

    # By value, so ZoneLights compare as the zone manager expects (numpy's == doesn't).
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PlacedLeds):
            return NotImplemented
        return (
            np.array_equal(self.pos, other.pos)
            and np.array_equal(self.local, other.local)
            and np.array_equal(self.local_u, other.local_u)
        )

    def __hash__(self) -> int:
        return hash(self.pos.tobytes())


@dataclass(frozen=True, eq=False)
class Space:
    """What a zone's effects know of the home around its LEDs (spec §5.1, §6.1).

    anchors: each anchor's position, (3,). anchor_points: every point of each anchor,
    (k, 3), so the speaker pair has two. rooms: room ids, indexed by LedSet.room.
    ceiling: metres, None without a map. centre: where unplaced lights gather when
    none of the zone's lights is placed.
    """

    anchors: Mapping[str, NDArray[np.float32]] = field(default_factory=_no_points)
    anchor_points: Mapping[str, NDArray[np.float32]] = field(default_factory=_no_points)
    rooms: tuple[str, ...] = ()
    ceiling: float | None = None
    centre: Vec3 | None = None

    # By value, so a map edit that leaves the geometry as it was (a rename, a light moved
    # elsewhere) leaves the running zones as they are.
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Space):
            return NotImplemented
        return (
            self.rooms == other.rooms
            and self.ceiling == other.ceiling
            and self.centre == other.centre
            and _same_points(self.anchors, other.anchors)
            and _same_points(self.anchor_points, other.anchor_points)
        )

    def __hash__(self) -> int:
        return hash((self.rooms, self.ceiling, self.centre, tuple(self.anchors)))


NO_SPACE = Space()


@dataclass(frozen=True, slots=True)
class LedSource:
    """One device's share of a zone: its id, LED count and own geometry, and where the
    home map puts its LEDs (None: not placed) in which room (an index into Space.rooms)."""

    device_id: str
    led_count: int
    geometry: DeviceGeometry | None = None
    placed: PlacedLeds | None = None
    room: int = NO_ROOM


@dataclass(frozen=True, eq=False)
class LedSet:
    pos: NDArray[np.float32]  # (N, 3) metres, x east, y south, z up
    npos: NDArray[np.float32]  # (N, 3) normalised to the zone's bounds
    local: NDArray[np.float32]  # (N, 3) normalised to each device's own bounds
    local_u: NDArray[np.float32]  # (N,) position along the device's LED order
    room: NDArray[np.int32]  # (N,) index into space.rooms, NO_ROOM for none
    device: NDArray[np.int32]  # (N,) index into `slices`
    slices: tuple[DeviceSlice, ...]
    space: Space = NO_SPACE

    @property
    def count(self) -> int:
        return int(self.pos.shape[0])

    @property
    def anchors(self) -> Mapping[str, NDArray[np.float32]]:
        return self.space.anchors

    @cached_property
    def bounds(self) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
        """The LEDs' lowest and highest corner; the origin for no LEDs."""
        if self.count == 0:
            origin = np.zeros(3, dtype=np.float32)
            return origin, origin
        return self.pos.min(axis=0), self.pos.max(axis=0)

    @cached_property
    def centre(self) -> NDArray[np.float32]:
        """The middle of the LEDs' bounds."""
        low, high = self.bounds
        middle: NDArray[np.float32] = ((low + high) / 2.0).astype(np.float32)
        return middle

    @cached_property
    def _by_device(self) -> Mapping[str, DeviceSlice]:
        return {piece.device_id: piece for piece in self.slices}

    def slice_for(self, device_id: str) -> DeviceSlice | None:
        return self._by_device.get(device_id)

    def subset(self, device_ids: Collection[str]) -> tuple[NDArray[np.intp], LedSet]:
        """Some devices' LEDs, in this set's order, and where they sit in it. Positions keep
        this set's normalisation, and a device left out keeps an empty slice, so `device`
        still indexes `slices`: an effect draws them as it would in the whole set."""
        parts: list[NDArray[np.intp]] = []
        slices: list[DeviceSlice] = []
        start = 0
        for piece in self.slices:
            count = piece.count if piece.device_id in device_ids else 0
            if count:
                parts.append(np.arange(piece.start, piece.stop, dtype=np.intp))
            slices.append(DeviceSlice(piece.device_id, start, start + count))
            start += count
        index = np.concatenate(parts) if parts else np.zeros(0, dtype=np.intp)
        return index, LedSet(
            pos=self.pos[index],
            npos=self.npos[index],
            local=self.local[index],
            local_u=self.local_u[index],
            room=self.room[index],
            device=self.device[index],
            slices=tuple(slices),
            space=self.space,
        )


def build_ledset(
    sources: Sequence[LedSource], space: Space = NO_SPACE, gap_m: float = DEVICE_GAP_M
) -> LedSet:
    positions: list[NDArray[np.float64]] = []
    locals_: list[NDArray[np.float64]] = []
    along: list[NDArray[np.float64]] = []
    owners: list[NDArray[np.int32]] = []
    rooms: list[NDArray[np.int32]] = []
    slices: list[DeviceSlice] = []
    loose: list[int] = []  # which entries of `positions` the map doesn't place
    cursor_x = 0.0
    start = 0
    for index, source in enumerate(sources):
        count = max(0, source.led_count)
        if count:
            placed = source.placed
            if placed is not None and placed.count == count:
                positions.append(placed.pos)
                locals_.append(placed.local)
                along.append(placed.local_u)
            else:
                local = _local_positions(source.geometry, count)
                low = local.min(axis=0)
                high = local.max(axis=0)
                laid = local - low
                laid[:, 0] += cursor_x
                cursor_x += float(high[0] - low[0]) + gap_m
                loose.append(len(positions))
                positions.append(laid)
                locals_.append(_normalise(local, low, high))
                along.append(steps_along(count))
            owners.append(np.full(count, index, dtype=np.int32))
            rooms.append(np.full(count, source.room, dtype=np.int32))
        slices.append(DeviceSlice(source.device_id, start, start + count))
        start += count
    _gather(positions, loose, space.centre)

    pos = np.concatenate(positions) if positions else np.zeros((0, 3))
    npos = _normalise(pos, pos.min(axis=0), pos.max(axis=0)) if len(pos) else pos
    return LedSet(
        pos=pos.astype(np.float32),
        npos=npos.astype(np.float32),
        local=(np.concatenate(locals_) if locals_ else np.zeros((0, 3))).astype(np.float32),
        local_u=(np.concatenate(along) if along else np.zeros(0)).astype(np.float32),
        room=np.concatenate(rooms) if rooms else np.zeros(0, dtype=np.int32),
        device=np.concatenate(owners) if owners else np.zeros(0, dtype=np.int32),
        slices=tuple(slices),
        space=space,
    )


def _gather(
    positions: list[NDArray[np.float64]], loose: Sequence[int], centre: Vec3 | None
) -> None:
    """Move the unplaced lights, as one group, so the middle of their bounds sits at the
    placed lights' mean, or at the home's centre when nothing is placed."""
    if not loose:
        return
    unplaced = set(loose)
    placed = [points for index, points in enumerate(positions) if index not in unplaced]
    if placed:
        target = np.concatenate(placed).mean(axis=0)
    elif centre is not None:
        target = np.asarray(centre, dtype=np.float64)
    else:
        return
    group = np.concatenate([positions[index] for index in loose])
    shift = target - (group.min(axis=0) + group.max(axis=0)) / 2.0
    for index in loose:
        positions[index] = positions[index] + shift


def steps_along(count: int) -> NDArray[np.float64]:
    """0..1 along `count` steps; a single step is 0 (local_u's convention)."""
    return np.arange(count) / (count - 1) if count > 1 else np.zeros(1)


def _normalise(
    values: NDArray[np.float64], low: NDArray[np.float64], high: NDArray[np.float64]
) -> NDArray[np.float64]:
    span = high - low
    out = np.full(values.shape, 0.5)
    spread = span > 1e-9
    out[:, spread] = (values[:, spread] - low[spread]) / span[spread]
    return out


def _local_positions(geometry: DeviceGeometry | None, count: int) -> NDArray[np.float64]:
    if isinstance(geometry, MatrixGeometry) and (
        sum(tile.width * tile.height for tile in geometry.tiles) == count
    ):
        grid = expand_positions(geometry, (0.0, 0.0, 0.0), count)
        return np.column_stack([grid[:, 0], np.zeros(count), grid[:, 1].max() - grid[:, 1]])
    if isinstance(geometry, StripGeometry):
        return expand_positions(geometry, (0.0, 0.0, 0.0), count)
    if count == 1:
        return np.zeros((1, 3))
    # No usable geometry: a point with several LEDs, a matrix whose size disagrees
    # with the LED count, or nothing at all.
    return np.column_stack([np.zeros(count), np.zeros(count), np.arange(count) * LED_PITCH_M])
