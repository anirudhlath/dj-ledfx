"""What particle effects share (spec §5.1): the particles of a moment, the random numbers
they're drawn from, the zone's lamps, and how particles light LEDs. Pure numpy.

A particle lights each LED by a Gaussian falloff with its distance, out to REACH radii,
and the LEDs add up what reaches them. Below GRID_FROM_LEDS LEDs every LED is measured
against every particle; from it on (spec §4.1: "Past about 2k LEDs, particles switch to a
spatial grid") only the LEDs in the grid cells around each particle are, with the same
colours.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

if TYPE_CHECKING:
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

F32 = NDArray[np.float32]
F64 = NDArray[np.float64]

REACH = 2.5  # a particle lights nothing past this many radii: under half an 8-bit step
GRID_FROM_LEDS = 2000  # from this many LEDs on, lit() looks only near each particle
SAME_STOP_M = 0.3  # lights whose middles are this close make one stop
CEILING_OVER_M = 0.5  # with no map, the ceiling is this far over the highest LED
MIN_RADIUS_M = 0.01  # a particle's light falls off over at least this
_GRID_SIZES = 8  # the grids a Ground keeps, one per cell size

_GOLDEN = np.uint64(0x9E3779B97F4A7C15)
_STREAMS = 0xD1B54A32D192ED03  # each stream starts this far on from the last
_MIX = (np.uint64(0xBF58476D1CE4E5B9), np.uint64(0x94D049BB133111EB))
_SHIFTS = (np.uint64(30), np.uint64(27), np.uint64(31))


@dataclass(frozen=True, eq=False, slots=True)
class Particles:
    """Where a particle effect's particles are at one moment: each one's position in
    metres on the map's axes, as the layer sees them (a layer's mirror or transform moves
    them with the LEDs), its colour 0..1 with its brightness in it, and its radius in
    metres, which sets how far its light falls (lit()). Oldest first."""

    pos: F32  # (P, 3)
    colour: F32  # (P, 3)
    radius: F32  # (P,)

    @property
    def count(self) -> int:
        return int(self.pos.shape[0])

    def newest(self, count: int) -> Particles:
        """The `count` newest: the last ones."""
        if self.count <= count:
            return self
        return Particles(self.pos[-count:], self.colour[-count:], self.radius[-count:])

    def pick(self, which: NDArray[np.bool_]) -> Particles:
        """The particles `which` marks, in order."""
        return Particles(self.pos[which], self.colour[which], self.radius[which])


def swarm(pos: ArrayLike, colour: ArrayLike, radius: ArrayLike) -> Particles:
    """Particles from positions (P, 3), colours (P, 3) or one colour (3,), and radii (P,)
    or one radius (at least MIN_RADIUS_M), as float32 arrays of their own."""
    where = np.array(pos, dtype=np.float32).reshape(-1, 3)
    count = len(where)
    colours = np.broadcast_to(np.asarray(colour, dtype=np.float32), (count, 3)).copy()
    radii = np.maximum(
        np.broadcast_to(np.asarray(radius, dtype=np.float32), (count,)), MIN_RADIUS_M
    )
    return Particles(where, colours, radii.astype(np.float32))


NO_PARTICLES = swarm(np.zeros((0, 3)), np.zeros((0, 3)), np.zeros(0))


def joined(*parts: Particles) -> Particles:
    """Several swarms as one, in order: the first's particles are the oldest."""
    return Particles(
        np.concatenate([part.pos for part in parts]),
        np.concatenate([part.colour for part in parts]),
        np.concatenate([part.radius for part in parts]),
    )


def _mix(x: NDArray[np.uint64]) -> NDArray[np.uint64]:
    """SplitMix64's finaliser: every bit of x stirred into every bit of the result."""
    x = (x ^ (x >> _SHIFTS[0])) * _MIX[0]
    x = (x ^ (x >> _SHIFTS[1])) * _MIX[1]
    mixed: NDArray[np.uint64] = x ^ (x >> _SHIFTS[2])
    return mixed


def draws(seed: int, keys: ArrayLike, count: int, stream: int = 0) -> F64:
    """`count` random numbers from 0 to 1 (1 left out) for each key, shape (keys, count),
    from the seed, the stream and the key alone: a key is an event (a particle, a beat's
    burst), so the same seed and key give the same numbers however the frames fall, and an
    effect gives each kind of event its own stream. ParamSettings._rng's counter-based
    twin, for many particles at once."""
    k = np.asarray(keys, dtype=np.int64).astype(np.uint64).reshape(-1, 1)
    j = np.arange(1, count + 1, dtype=np.uint64).reshape(1, -1)
    base = np.uint64((seed + stream * _STREAMS) % 2**64)
    first = _mix(k * _GOLDEN + base)
    bits = _mix(first + j * _GOLDEN)
    values: F64 = (bits >> np.uint64(11)).astype(np.float64) * 2.0**-53
    return values


def recent(now: float, every: float, life: float) -> NDArray[np.int64]:
    """The events that may be alive at `now`: event n comes at (n + u) * every, u from 0 to
    1, and lives `life`. In seconds or in beats alike."""
    first = math.floor((now - life) / every) - 1
    return np.arange(first, math.floor(now / every) + 1, dtype=np.int64)


WANDER_DRAWS = 12  # the random numbers a wanderer takes


def wander(u: F64, t: float, speed: float, low: ArrayLike, high: ArrayLike) -> F64:
    """Where each wanderer is at time t, inside the box from low to high (one box, (3,), or
    one each, (wanderers, 3)): two slow waves on each axis, of periods and phases from its
    WANDER_DRAWS random numbers (a row of u), so it moves smoothly and never repeats for
    long, at about `speed` metres a second. Shape (wanderers, 3)."""
    low64, high64 = np.asarray(low, dtype=np.float64), np.asarray(high, dtype=np.float64)
    half = np.maximum((high64 - low64) / 2.0, 0.05)
    rate = (0.6 + 0.8 * u[:, :6]).reshape(-1, 2, 3) * (speed / half)[..., None, :]  # rad/s
    phase = 2.0 * math.pi * u[:, 6:].reshape(-1, 2, 3)
    waves = np.sin(rate * t + phase)
    where: F64 = (low64 + high64) / 2.0 + half * (0.6 * waves[:, 0] + 0.4 * waves[:, 1])
    return where


def arc(start: ArrayLike, end: ArrayLike, share: ArrayLike, rise: ArrayLike) -> F64:
    """Points `share` (0..1) of the way from start to end, each on a parabola that rises
    `rise` metres over the straight line half-way: a hop, a bounce or a throw. With share in
    proportion to the time, it's a thrown thing's path. Shape (points, 3)."""
    a, b = np.asarray(start, dtype=np.float64), np.asarray(end, dtype=np.float64)
    part = np.asarray(share, dtype=np.float64)
    where: F64 = np.array(a + (b - a) * part[..., None], dtype=np.float64, ndmin=2)
    where[:, 2] += (4.0 * np.asarray(rise) * part * (1.0 - part)).ravel()
    return where


TOURS = 1000  # tour k draws from stream TOURS + k


def tour(seed: int, key: int, step: int, stops: int) -> int:
    """The stop tour `key` is at on its step `step`, of `stops` stops (at least one): each
    round of `stops` steps visits every stop once, in an order of its own, and a tour never
    stays on one stop two steps running (with two stops it goes to and fro, with one it
    stays)."""
    if stops < 3:
        return step % stops
    round_, place = divmod(step, stops)
    order = shuffled(seed, key, round_, stops)
    if place < 2 and order[0] == shuffled(seed, key, round_ - 1, stops)[-1]:
        order[[0, 1]] = order[[1, 0]]
    return int(order[place])


def shuffled(seed: int, key: int, round_: int, stops: int) -> NDArray[np.intp]:
    """Round `round_` of tour `key`: the stops in the order its random numbers put them."""
    order: NDArray[np.intp] = np.argsort(
        draws(seed, [round_], stops, stream=TOURS + key)[0], kind="stable"
    )
    return order


def spread_over(seed: int, count: int, stops: int) -> NDArray[np.intp]:
    """The stop each of `count` things takes, of `stops` (at least one): every stop once
    before any twice, in an order the seed picks."""
    taken: NDArray[np.intp] = shuffled(seed, 0, 0, stops)[np.arange(count) % stops]
    return taken


@dataclass(frozen=True, eq=False, slots=True)
class Lamps:
    """The zone's lamps, where particles find them (spec §5.1: emitters, paths and targets
    can be lamps). One stop for each light, and one for lights whose middles are within
    SAME_STOP_M of one another (a device's parts share its placement): each stop's middle,
    the heights of its lowest and highest LED, and its LEDs."""

    centre: F32  # (S, 3)
    low: F32  # (S,)
    high: F32  # (S,)
    members: NDArray[np.intp]  # the zone's LEDs, stop by stop, each stop's in zone order
    starts: NDArray[np.intp]  # (S + 1,): stop s's LEDs are members[starts[s]:starts[s + 1]]

    @property
    def count(self) -> int:
        return int(self.centre.shape[0])

    def pick(self, u: ArrayLike) -> NDArray[np.intp]:
        """The stop each u (0..1) picks, each stop alike."""
        picked: NDArray[np.intp] = np.minimum(
            (np.asarray(u, dtype=np.float64) * self.count).astype(np.intp), self.count - 1
        )
        return picked

    def led(self, stop: ArrayLike, u: ArrayLike) -> NDArray[np.intp]:
        """An LED of each stop, the one u (0..1) picks of its LEDs: its index in the zone."""
        stops = np.asarray(stop, dtype=np.intp)
        first, many = self.starts[stops], self.starts[stops + 1] - self.starts[stops]
        place = np.minimum((np.asarray(u, dtype=np.float64) * many).astype(np.intp), many - 1)
        led: NDArray[np.intp] = self.members[first + place]
        return led


NO_LAMPS = Lamps(
    np.zeros((0, 3), np.float32),
    np.zeros(0, np.float32),
    np.zeros(0, np.float32),
    np.zeros(0, np.intp),
    np.zeros(1, np.intp),
)


def lamps_of(leds: LedSet) -> Lamps:
    """The stops the LEDs make, in the zone's order: each light's LEDs, joined with the
    stop before whose first light's middle is within SAME_STOP_M."""
    groups: list[list[NDArray[np.intp]]] = []
    firsts: list[NDArray[np.float32]] = []
    for piece in leds.slices:
        if piece.count == 0:
            continue
        middle = leds.pos[piece.start : piece.stop].mean(axis=0)
        near = next(
            (i for i, first in enumerate(firsts) if np.linalg.norm(first - middle) <= SAME_STOP_M),
            None,
        )
        which = np.arange(piece.start, piece.stop, dtype=np.intp)
        if near is None:
            firsts.append(middle)
            groups.append([which])
        else:
            groups[near].append(which)
    if not groups:
        return NO_LAMPS
    members = [np.concatenate(group) for group in groups]
    heights = [leds.pos[which, 2] for which in members]
    return Lamps(
        centre=np.array(
            [np.mean([leds.pos[w].mean(axis=0) for w in group], axis=0) for group in groups],
            dtype=np.float32,
        ),
        low=np.array([z.min() for z in heights], dtype=np.float32),
        high=np.array([z.max() for z in heights], dtype=np.float32),
        members=np.concatenate(members),
        starts=np.cumsum([0, *(len(which) for which in members)]).astype(np.intp),
    )


def around(points: F32, middle: NDArray[np.floating[Any]]) -> NDArray[np.intp]:
    """The points' order round the middle, seen from above: a loop round the room."""
    offset = points[:, :2].astype(np.float64) - np.asarray(middle, dtype=np.float64)[:2]
    order: NDArray[np.intp] = np.argsort(np.arctan2(offset[:, 1], offset[:, 0]), kind="stable")
    return order


@dataclass(frozen=True, slots=True)
class _Grid:
    """The LEDs sorted by grid cell: the cells' keys in order, the LEDs in that order, and
    how keys are made (the origin, the cell size and the cell counts along each axis)."""

    keys: NDArray[np.int64]
    order: NDArray[np.intp]
    origin: F32
    size: float
    dims: NDArray[np.int64]

    def key(self, cells: NDArray[np.int64]) -> NDArray[np.int64]:
        """Each cell's key; a cell outside the grid is one of its edge cells, which hold no
        LEDs."""
        cells = np.clip(cells, 0, self.dims - 1)
        keys: NDArray[np.int64] = (cells[..., 0] * self.dims[1] + cells[..., 1]) * self.dims[
            2
        ] + cells[..., 2]
        return keys

    def cells(self, points: F32) -> NDArray[np.int64]:
        cells: NDArray[np.int64] = np.floor((points - self.origin) / np.float32(self.size)).astype(
            np.int64
        )
        return cells


_NEIGHBOURS = np.array(
    [(x, y, z) for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1)], dtype=np.int64
)


@dataclass(frozen=True, eq=False)
class Ground:
    """Where a particle effect's particles move, worked out once for each LED set: the
    LEDs, their lamps, the zone's frame (the set's bounds, which a layer's view keeps), its
    floor and its ceiling. The floor is the map's (height 0) and the ceiling the map's
    under a map; with none, the lowest LED and CEILING_OVER_M over the highest."""

    leds: LedSet
    lamps: Lamps
    floor: float
    ceiling: float
    _grids: dict[float, _Grid] = field(default_factory=dict)

    @classmethod
    def of(cls, leds: LedSet) -> Ground:
        low, high = leds.bounds
        ceiling = leds.space.ceiling
        if ceiling is not None and ceiling > 0.0:
            return cls(leds, lamps_of(leds), 0.0, float(ceiling))
        return cls(leds, lamps_of(leds), float(low[2]), float(high[2]) + CEILING_OVER_M)

    @property
    def low(self) -> F32:
        return self.leds.bounds[0]

    @property
    def high(self) -> F32:
        return self.leds.bounds[1]

    @property
    def centre(self) -> F32:
        return self.leds.centre

    def on(self, stop: ArrayLike, u: ArrayLike) -> F64:
        """Where an LED of each stop is: the one u (0..1) picks (Lamps.led), so particles
        spread along a long light as they do round a short one."""
        on: F64 = self.leds.pos[self.lamps.led(stop, u)].astype(np.float64)
        return on

    def foot(self, stop: ArrayLike, u: ArrayLike) -> F64:
        """An LED of each stop seen from above (the one u picks, as on() picks it), down at
        the height of the stop's lowest LED: where a thing rising up the lamp starts, or
        one landing on it lands."""
        foot = self.on(stop, u)
        foot[..., 2] = self.lamps.low[np.asarray(stop, dtype=np.intp)]
        return foot

    def box(self, margin: float = 0.0, around: ArrayLike | None = None) -> tuple[F64, F64]:
        """Where particles that roam stay: the zone's frame `margin` metres wider each way,
        or `margin` each way round each point (shape (3,) or (P, 3)), between the floor and
        the ceiling."""
        if around is None:
            low, high = self.low.astype(np.float64), self.high.astype(np.float64)
        else:
            low = high = np.asarray(around, dtype=np.float64)
        low, high = low - margin, high + margin
        low[..., 2] = np.maximum(low[..., 2], self.floor)
        high[..., 2] = np.minimum(high[..., 2], self.ceiling)
        return low, high

    @cached_property
    def _from_centre(self) -> tuple[F32, F32]:
        """Each LED's place from the frame's centre, and its square length."""
        pos: F32 = (self.leds.pos - self.centre).astype(np.float32)
        return pos, np.einsum("ij,ij->i", pos, pos)

    def grid(self, size: float) -> _Grid:
        """The LEDs in cells at least `size` wide (a power of √2 metres, so only a few
        sizes are ever kept), each LED at least one cell in from the grid's edge."""
        width = 2.0 ** (math.ceil(2.0 * math.log2(max(size, 0.01))) / 2.0)
        grid = self._grids.get(width)
        if grid is None:
            if len(self._grids) >= _GRID_SIZES:
                self._grids.clear()
            # From the LEDs' own lowest corner, not the frame's: a layer's mirror or transform
            # can move them below the frame.
            low = self.leds.pos.min(axis=0) if self.leds.count else self.low
            origin = (low - np.float32(width)).astype(np.float32)
            cells = np.floor((self.leds.pos - origin) / np.float32(width)).astype(np.int64)
            np.maximum(cells, 1, out=cells)  # rounding never puts an LED in an edge cell
            dims = cells.max(axis=0) + 2 if len(cells) else np.full(3, 2, dtype=np.int64)
            unsorted = _Grid(np.zeros(0, np.int64), np.zeros(0, np.intp), origin, width, dims)
            keys = unsorted.key(cells)
            order = np.argsort(keys, kind="stable")
            grid = self._grids[width] = _Grid(keys[order], order, origin, width, dims)
        return grid


def lit(ground: Ground, particles: Particles) -> FloatRGB:
    """Each LED's light from the particles (spec §5.1: "Particles light LEDs by distance
    falloff"): the sum of each particle's colour times exp(-(d / r)²), d its distance from
    the LED and r its radius, out to REACH radii, and at most 1. A new float32 array."""
    count = ground.leds.count
    out = np.zeros((count, 3), dtype=np.float32)
    if count == 0 or particles.count == 0:
        return out
    if count < GRID_FROM_LEDS:
        _densely(ground, particles, out)
    else:  # the grid's cells fit the usual sizes; the few far larger light every LED anyway
        large = particles.radius > np.float32(2.0) * np.median(particles.radius)
        if large.any():
            _densely(ground, particles.pick(large), out)
            particles = particles.pick(~large)
        _by_grid(ground, particles, out)
    np.minimum(out, np.float32(1.0), out=out)
    return out


def _densely(ground: Ground, particles: Particles, out: FloatRGB) -> None:
    """Every LED against every particle, as one matrix product."""
    pos, square = ground._from_centre
    at = (particles.pos - ground.centre).astype(np.float32)
    gap = square[:, None] + np.einsum("ij,ij->i", at, at)[None, :] - 2.0 * (pos @ at.T)
    np.maximum(gap, np.float32(0.0), out=gap)  # (N, P) square distances
    reach = particles.radius * particles.radius
    weight = np.exp(-gap / reach)
    weight[gap > np.float32(REACH * REACH) * reach] = 0.0
    out += (weight @ particles.colour).astype(np.float32)


def _by_grid(ground: Ground, particles: Particles, out: FloatRGB) -> None:
    """Only the LEDs in the 27 cells round each particle's, the cells REACH radii of the
    largest particle wide: each pair of a particle and an LED near it, gathered at once."""
    if particles.count == 0:
        return
    grid = ground.grid(REACH * float(particles.radius.max()))
    near = grid.key(grid.cells(particles.pos)[:, None, :] + _NEIGHBOURS[None, :, :])  # (P, 27)
    first = np.searchsorted(grid.keys, near, side="left").ravel()
    many = np.searchsorted(grid.keys, near, side="right").ravel() - first
    pairs = int(many.sum())
    if pairs == 0:
        return
    whose = np.repeat(np.repeat(np.arange(particles.count), len(_NEIGHBOURS)), many)
    step = np.arange(pairs) - np.repeat(np.cumsum(many) - many, many)
    led = grid.order[np.repeat(first, many) + step]
    gap = ground.leds.pos[led] - particles.pos[whose]
    square = np.einsum("ij,ij->i", gap, gap)
    reach = particles.radius[whose] * particles.radius[whose]
    weight = np.exp(-square / reach)
    weight[square > np.float32(REACH * REACH) * reach] = 0.0
    for channel in range(3):
        out[:, channel] += np.bincount(
            led, weights=weight * particles.colour[whose, channel], minlength=len(out)
        ).astype(np.float32)
