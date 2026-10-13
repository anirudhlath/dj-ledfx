"""What particle effects share (spec §5.1): the particles of a moment, the random numbers
they're drawn from, the zone's lamps, how an effect that makes particles lamp by lamp keeps to
the cap, and how particles light LEDs. Pure numpy.

A particle lights each LED by a Gaussian falloff with its distance, out to REACH radii,
and the LEDs add up what reaches them. Below GRID_FROM_LEDS LEDs every LED is measured
against every particle; from it on (spec §4.1: "Past about 2k LEDs, particles switch to a
spatial grid", and measured, the grid is no dearer from 600: see GRID_FROM_LEDS) only the
LEDs in the grid cells around each particle are, with the same colours.
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
# From this many LEDs on, lit() looks only near each particle. The spec says "about 2k" (§4.1).
# Measured with 500 particles, the grid costs no more than the dense sum from 600 LEDs (0.7 ms
# against 0.9 for radii of 0.2 m, 1.1 against 1.1 for 0.6 m), and the dense sum keeps growing
# with the LEDs: 2.7 ms at 1800, the half of §4.1's 5 ms that each look of a transition gets
# (§5.3: both are rendered), and 4.4 ms at 3000.
GRID_FROM_LEDS = 600
SAME_STOP_M = 0.3  # lights whose middles are this close make one stop
CEILING_OVER_M = 0.5  # with no map, the ceiling is this far over the highest LED
WINDOW_MIN = 0.25  # a lamp's events are born in this share of their stretches at the least
ROOM_MARGIN = 0.01  # of an event, left over in a lamp's share of the room: no count tips over
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
        """The `count` newest: the last ones; none for a count of 0 or less."""
        if count <= 0:
            return NO_PARTICLES
        if self.count <= count:
            return self
        return Particles(self.pos[-count:], self.colour[-count:], self.radius[-count:])

    def pick(self, which: NDArray[np.bool_] | NDArray[np.intp]) -> Particles:
        """The particles `which` marks (a mask) or names (indices), in that order."""
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


def in_birth_order(*parts: tuple[Particles, F64]) -> Particles:
    """Several swarms as one, oldest first: each part is its particles and when each of them
    was born, in seconds. Particles born together keep the order of the parts."""
    whole = joined(*(particles for particles, _ in parts))
    return whole.pick(np.argsort(np.concatenate([born for _, born in parts]), kind="stable"))


def _mix(x: NDArray[np.uint64]) -> NDArray[np.uint64]:
    """SplitMix64's finaliser: every bit of x stirred into every bit of the result."""
    x = (x ^ (x >> _SHIFTS[0])) * _MIX[0]
    x = (x ^ (x >> _SHIFTS[1])) * _MIX[1]
    mixed: NDArray[np.uint64] = x ^ (x >> _SHIFTS[2])
    return mixed


def draws(seed: int, keys: ArrayLike, count: int, stream: ArrayLike = 0) -> F64:
    """`count` random numbers from 0 to 1 (1 left out) for each key, shape (keys, count),
    from the seed, the stream and the key alone: a key is an event (a particle, a beat's
    burst), so the same seed and key give the same numbers however the frames fall, and an
    effect gives each kind of event its own stream (one for all the keys, or one for each of
    them). ParamSettings._rng's counter-based twin, for many particles at once."""
    k = np.asarray(keys, dtype=np.int64).astype(np.uint64).reshape(-1, 1)
    j = np.arange(1, count + 1, dtype=np.uint64).reshape(1, -1)
    s = np.asarray(stream, dtype=np.int64).astype(np.uint64).reshape(-1, 1)
    base = np.uint64(seed % 2**64) + s * np.uint64(_STREAMS)  # (seed + stream * _STREAMS) % 2**64
    first = _mix(k * _GOLDEN + base)
    bits = _mix(first + j * _GOLDEN)
    values: F64 = (bits >> np.uint64(11)).astype(np.float64) * 2.0**-53
    return values


def recent(now: float, every: float, life: float) -> NDArray[np.int64]:
    """The events that may be alive at `now`: event n comes at (n + u) * every, u from 0 to
    2 (a lamp's events come up to a stretch late: Streams.born), and lives `life`. In seconds
    or in beats alike."""
    first = math.floor((now - life) / every) - 1
    return np.arange(first, math.floor(now / every) + 1, dtype=np.int64)


def fired(beats: float, life: float) -> NDArray[np.int64]:
    """The whole beats whose bursts are in the air at `beats`, oldest first: beat j is, from
    the beat itself (0 <= beats - j) until `life` beats on (beats - j < life)."""
    first = recent(beats, 1.0, life)
    alive: NDArray[np.int64] = first[beats - first < life]  # recent() stops at the last beat
    return alive


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


def rise_under(ceiling: ArrayLike, start: ArrayLike, end: ArrayLike, rise: ArrayLike) -> F64:
    """`rise`, held to the most an arc (above) between heights `start` and `end` can rise and
    keep its top at or under `ceiling`: the exact fit, which is more than the room over the
    higher end. An arc rising r over the line between ends a and b (d apart in height) tops
    out at (a + b) / 2 + r + d² / 16r, or at its higher end when r is under |d| / 4, so the
    most is (√(C - a) + √(C - b))² / 4: all of the room over equal ends, and a quarter of the
    climb to an end at the ceiling. An end over the ceiling counts as at it, so no room is a
    rise of nothing. Heights broadcast."""
    top = np.asarray(ceiling, dtype=np.float64)
    over_start = np.sqrt(np.maximum(top - np.asarray(start, dtype=np.float64), 0.0))
    over_end = np.sqrt(np.maximum(top - np.asarray(end, dtype=np.float64), 0.0))
    most: F64 = np.minimum(rise, np.square(over_start + over_end) / 4.0)
    return most


def in_ball(up: ArrayLike, turn: ArrayLike, depth: ArrayLike, radius: float) -> F64:
    """Points spread evenly through a ball of `radius` metres round the origin, one for each
    row of random numbers from 0 to 1: `up` picks the height (evenly, from the bottom to the
    top, which spreads the points evenly over the ball's surface), `turn` the way round it (in
    turns) and `depth` how far out (as its cube root, which fills the ball's volume evenly).
    Shape (points, 3)."""
    height = 2.0 * np.asarray(up, dtype=np.float64) - 1.0
    side = 2.0 * math.pi * np.asarray(turn, dtype=np.float64)
    flat = np.sqrt(1.0 - height * height)
    far = (radius * np.cbrt(np.asarray(depth, dtype=np.float64)))[:, None]
    ball: F64 = far * np.stack([flat * np.cos(side), flat * np.sin(side), height], axis=1)
    return ball


TOURS = 1000  # tour k draws from stream TOURS + k


def tour(seed: int, key: ArrayLike, step: ArrayLike, stops: int) -> NDArray[np.intp]:
    """The stop each tour `key` is at on its step `step` (as many as the two broadcast to),
    of `stops` stops (at least one): each round of `stops` steps visits every stop once, in
    an order of its own, and a tour never stays on one stop two steps running (with two
    stops it goes to and fro, with one it stays)."""
    keys, steps = np.broadcast_arrays(
        np.asarray(key, dtype=np.int64), np.asarray(step, dtype=np.int64)
    )
    if stops < 3:
        return np.asarray(steps % stops, dtype=np.intp)
    round_, place = np.divmod(steps, stops)
    order = shuffled(seed, keys, round_, stops)
    last = shuffled(seed, keys, round_ - 1, stops)[..., -1]
    # A round that would open on the stop the one before closed on swaps its first two stops.
    place = np.where((place < 2) & (order[..., 0] == last), 1 - place, place)
    at: NDArray[np.intp] = np.take_along_axis(order, place[..., None], axis=-1)[..., 0]
    return at


def shuffled(seed: int, key: ArrayLike, round_: ArrayLike, stops: int) -> NDArray[np.intp]:
    """Round `round_` of tour `key`: the stops in the order its random numbers put them, a
    row of `stops` for each key and round (as many as the two broadcast to)."""
    keys, rounds = np.broadcast_arrays(
        np.asarray(key, dtype=np.int64), np.asarray(round_, dtype=np.int64)
    )
    u = draws(seed, rounds.ravel(), stops, stream=TOURS + keys.ravel())
    order: NDArray[np.intp] = np.argsort(u, axis=1, kind="stable").reshape(*keys.shape, stops)
    return order


def spread_over(seed: int, count: int, stops: int) -> NDArray[np.intp]:
    """The stop each of `count` things takes, of `stops` (at least one): every stop once
    before any twice, in an order the seed picks."""
    taken: NDArray[np.intp] = shuffled(seed, 0, 0, stops)[np.arange(count) % stops]
    return taken


LAMP_KEYS = 65536  # event n of lamp s draws from key n * LAMP_KEYS + s
STARTS = 900  # the stream the lamps' starts are drawn from


@dataclass(frozen=True, eq=False, slots=True)
class Alive:
    """The events of lamps (embers, drops) that are alive at one moment, oldest first."""

    lamp: NDArray[np.intp]  # each event's lamp
    u: F64  # (events, draws): each event's own random numbers
    born: F64  # when each was born, in seconds
    age: F64  # seconds since
    share: F64  # how far through its life each is, from 0 to 1 (1 left out)


@dataclass(frozen=True, eq=False, slots=True)
class Streams:
    """The events (embers climbing, drops running) that lamps make, from lamp_streams."""

    lamp: NDArray[np.intp]  # the lamps that make events, in order
    rate: float  # events to a usual life, for each of them
    window: float  # the share of its stretch that an event is born in
    start: F64  # (lamps,): where in its stretch each lamp's window starts, as a share of it
    spread: float  # a life is its usual one give or take half of this share of it

    def events(self, n: NDArray[np.int64]) -> tuple[NDArray[np.int64], NDArray[np.intp]]:
        """Events n of every lamp that makes them, n by n: each event's n, and its lamp."""
        return np.repeat(n, len(self.lamp)), np.tile(self.lamp, len(n))

    def born(self, event: NDArray[np.int64], lamp: NDArray[np.intp], u: F64) -> F64:
        """When each event is born, in stretches: event + start + window * u, u its own draw."""
        born: F64 = event + self.start[lamp] + self.window * u
        return born

    def alive(self, seed: int, t: float, usual: float, count: int) -> Alive:
        """The events alive at time t, a usual life being `usual` seconds, with `count` random
        numbers drawn for each from the key of its lamp and its n alone (draws), so an event is
        where it is whenever it is drawn. Column 0 of u sets its birth in its window, and
        column 1 its life, between 1 - spread / 2 and 1 + spread / 2 usual lives (a spread of 0
        leaves the column to the effect). Oldest first."""
        every = usual / self.rate  # one event leaves each lamp this often
        n = recent(t, every, usual * (1.0 + self.spread / 2.0))
        event, lamp = self.events(n)
        u = draws(seed, event * LAMP_KEYS + lamp, count)
        born = self.born(event, lamp, u[:, 0]) * every
        age = t - born
        share = age / (usual * (1.0 - self.spread / 2.0 + self.spread * u[:, 1]))
        alive = np.flatnonzero((age >= 0.0) & (share < 1.0))
        alive = alive[np.argsort(born[alive], kind="stable")]
        return Alive(lamp[alive], u[alive], born[alive], age[alive], share[alive])


def lamp_streams(seed: int, lamps: int, rate: float, spread: float, room: int) -> Streams:
    """How `lamps` lamps make events (embers, drops) so that no more than `room` are alive at
    once, however many lamps there are and however the draws fall.

    Each lamp makes one event in each stretch of `every` seconds, `rate` events to a usual
    life: event n is born at (n + start + window * u) * every, u from 0 to 1 its own draw, and
    lives `longest` usual lives at the most, `longest` being 1 + spread / 2. Born anywhere in
    their stretches (window 1, start 0, as recent() has them), a lamp's events can come to
    ceil(longest * rate + 1) alive at once; born in a `window` of them, ceil(longest * rate +
    window). The lamps share the room in whole events, `room // served` each, and a rate that
    fits that is left as it was, with the window narrowed as far as WINDOW_MIN to make it
    fit; past that the rate comes down. Both are the same for every lamp, and each lamp's
    window starts at a place of its own in the stretch, so the lamps are not in step.
    ROOM_MARGIN keeps a rounding from tipping a count that comes out even. With more lamps
    than room, a seeded `room` of them make events (as snow gives its flakes to as many lamps
    as it has) and the others make none."""
    longest = 1.0 + spread / 2.0
    served = min(lamps, room)
    if served <= 0:
        return Streams(np.zeros(0, np.intp), rate, 1.0, np.zeros(max(lamps, 0)), spread)
    slack = room // served - ROOM_MARGIN  # what a lamp's longest count must stay under
    window = min(1.0, slack - longest * rate)
    if window < WINDOW_MIN:
        window, rate = WINDOW_MIN, (slack - WINDOW_MIN) / longest
    lamp = (
        np.arange(lamps, dtype=np.intp)
        if lamps <= room
        else np.sort(spread_over(seed, room, lamps))
    )
    start = np.zeros(lamps)
    if window < 1.0:
        start[lamp] = draws(seed, lamp, 1, stream=STARTS)[:, 0]
    return Streams(lamp, rate, window, start, spread)


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
    under a map; with none, the lowest LED and CEILING_OVER_M over the highest. A lamp the
    map (or a layer's transform) puts outside them, as far as float32 (which the LEDs are held
    in) can tell, has a floor and a ceiling of its own (floor_for, ceiling_for): what moves
    along a lamp takes in all of its LEDs."""

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

    def floor_for(self, stop: ArrayLike) -> F64:
        """The lowest a thing goes at each stop's lamp: the floor, or the lamp's own lowest
        LED where the map (or a layer's transform) puts the lamp under it. What runs past a
        lamp stops at the floor, but never short of the lamp. Under it is decided in float32,
        as the LEDs are held: a lamp whose lowest LED is at the floor (0.7, which float32 holds
        a little under) keeps the floor itself, to the last bit."""
        low = self.lamps.low[np.asarray(stop, dtype=np.intp)]
        floor: F64 = np.where(low < np.float32(self.floor), low.astype(np.float64), self.floor)
        return floor

    def ceiling_for(self, stop: ArrayLike) -> F64:
        """The highest a thing goes at each stop's lamp: the ceiling, or the lamp's own
        highest LED where the map (or a layer's transform) puts the lamp over it. Over it is
        decided in float32, as the LEDs are held: a lamp whose highest LED is at the ceiling
        (2.45, which float32 holds a little over) keeps the ceiling itself, to the last bit."""
        high = self.lamps.high[np.asarray(stop, dtype=np.intp)]
        ceiling: F64 = np.where(
            high > np.float32(self.ceiling), high.astype(np.float64), self.ceiling
        )
        return ceiling

    def within(self, stop: ArrayLike, z: ArrayLike) -> F64:
        """The heights z (one for each stop) held between the floor and the ceiling of the
        stop's lamp (floor_for, ceiling_for): what goes to a lamp stops at the floor and the
        ceiling, but never short of the lamp's own LEDs."""
        held: F64 = np.clip(
            np.asarray(z, dtype=np.float64), self.floor_for(stop), self.ceiling_for(stop)
        )
        return held

    def box(
        self, margin: float = 0.0, around: ArrayLike | None = None, stops: ArrayLike | None = None
    ) -> tuple[F64, F64]:
        """Where particles that roam stay: the zone's frame `margin` metres wider each way,
        or `margin` each way round each point (shape (3,) or (P, 3)), between the floor and
        the ceiling. Round points that are LEDs of lamps (`stops`, a lamp for each point, so
        it needs `around`, the points), a box takes in the whole lamp where it stands outside
        them (floor_for, ceiling_for)."""
        if stops is not None and around is None:
            raise ValueError("box() takes stops only with around, the points they go with")
        if around is None:
            low, high = self.low.astype(np.float64), self.high.astype(np.float64)
        else:
            low = high = np.asarray(around, dtype=np.float64)
        low, high = low - margin, high + margin
        low[..., 2] = np.maximum(
            low[..., 2], self.floor if stops is None else self.floor_for(stops)
        )
        high[..., 2] = np.minimum(
            high[..., 2], self.ceiling if stops is None else self.ceiling_for(stops)
        )
        return low, high

    @cached_property
    def _from_centre(self) -> tuple[F64, F64]:
        """Each LED's place from the frame's centre, and its square length, in float64: _densely
        takes small differences of these."""
        pos: F64 = self.leds.pos.astype(np.float64) - self.centre.astype(np.float64)
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
    the LED and r its radius, out to REACH radii, and at most 1. A new float32 array.

    Measured on one core, 500 particles take 0.9 ms on 599 LEDs (the dense sum) and 1.5 ms on
    10k LEDs when their radius is 0.2 m (the grid): inside spec §4.1's 5 ms. The grid's cells
    are REACH radii wide, so a larger radius gathers more LEDs for each particle: 500 of
    0.6 m on 10k LEDs take 8 to 11 ms (the allocator's page faults decide), over it. That is
    documented, not mended.

    A particle with a NaN or infinite place or size sends the frame the dense way whatever the
    LED count, so a NaN reaches the frame (spec §8: a look that produces NaN is crashed) and no
    grid cell is made of it."""
    count = ground.leds.count
    out = np.zeros((count, 3), dtype=np.float32)
    if count == 0 or particles.count == 0:
        return out
    if count < GRID_FROM_LEDS or not _finite(particles):
        _densely(ground, particles, out)
    else:  # the grid's cells fit the usual sizes; the few far larger light every LED anyway
        large = particles.radius > np.float32(2.0) * np.median(particles.radius)
        if large.any():
            _densely(ground, particles.pick(large), out)
            particles = particles.pick(~large)
        _by_grid(ground, particles, out)
    np.minimum(out, np.float32(1.0), out=out)
    return out


def _finite(particles: Particles) -> bool:
    """Whether every particle's place and size are finite numbers: the grid files each particle
    by them, and a NaN or an infinity has no cell."""
    return bool(np.isfinite(particles.pos).all() and np.isfinite(particles.radius).all())


def _densely(ground: Ground, particles: Particles, out: FloatRGB) -> None:
    """Every LED against every particle, as one matrix product. The square distances are
    |a|² + |b|² - 2a·b from the frame's centre, worked out in float64: in float32 that loses
    the small ones (a particle on an LED, far from the centre) by several 8-bit steps.

    An array with an entry for each LED and particle is megabytes, and a new one for every
    step took three times as long as working in place, so the steps work in place."""
    pos, square = ground._from_centre
    at = particles.pos.astype(np.float64) - ground.centre.astype(np.float64)
    gap = pos @ (-2.0 * at).T  # (N, P): -2a·b
    gap += square[:, None]
    gap += np.einsum("ij,ij->i", at, at)
    exponent = np.empty(gap.shape, dtype=np.float32)  # float32 is plenty from here
    np.maximum(gap, 0.0, out=exponent, casting="same_kind")
    exponent *= np.float32(-1.0) / (particles.radius * particles.radius)  # -(d / r)²
    past = exponent < np.float32(-REACH * REACH)
    weight = np.exp(exponent, out=exponent)
    weight[past] = 0.0
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
