"""Flock's particles (looks.json "flock").

The flock flies from lamp to lamp on a tour (particle_tools.tour), MOVE_BARS bars from one
to the next, easing in and out, so it gathers on each lamp in turn, round an LED of it (any
of its LEDs, its own each visit). Each bird keeps its own place in the flock, within
spread_m of its middle, and the whole flock turns about its middle once every SWIRL_BARS
bars. On the downbeat of every other bar, as the flock comes to a lamp, the birds burst out
to `scatter` times their places and gather again over the next few beats.

Heights: the birds keep between the floor and the ceiling, widened to take in the lamp's own
LEDs where the map (or a layer's transform) puts a lamp outside them (Ground.floor_for and
ceiling_for). The flock is FLAT flatter than it is wide, and its height is fitted to the room
over and under its middle rather than clipped to it: the farthest a bird can go up or down is
scaled to the room on that side when it is more, so the birds spread through the room left
instead of piling up on the ceiling or the floor, and a side with room is left as it is. With
no room on a side (a band not around the lamp, which Ground never gives) the birds that go
that way stay level with the middle. The band is the one between its two lamps' bands that
the flock moves through with its middle, so it is its lamp's own band wherever the flock
gathers and stays inside the union of the two on the way. A band that jumped at the downbeat
from one pair of lamps to the next would pop the birds' height there.

The count is the `count` setting, at most 200 and so within MAX_PARTICLES, whatever the
lamps: each bird is its own, and none is dealt out among the lamps.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.color import palette_at
from dj_ledfx.effects.easing import ease_in_out
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.effects.particle_tools import draws, swarm, tour
from dj_ledfx.effects.particles import ParamParticles
from dj_ledfx.tempo.model import BEATS_PER_BAR

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.particle_tools import Ground, Particles

FLOCK_PALETTE = ("#fff0c8", "#ffb464", "#ff6482")
MOVE_BARS = 2  # the flock takes this many bars from one lamp to the next
SWIRL_BARS = 2.0  # it turns once in this many bars
SCATTER_BEATS = 0.75  # a scatter is widest this many beats after its downbeat
FLAT = 0.5  # a flock is this much flatter than it is wide


def scattered(since: float, scatter: float) -> float:
    """How far out the birds are, as a share of their places, `since` beats after the
    downbeat that scatters them: out to `scatter` at SCATTER_BEATS, then back."""
    rise = since / SCATTER_BEATS
    return 1.0 + (scatter - 1.0) * rise * math.exp(1.0 - rise)


def _fit(room: float, farthest: float) -> float:
    """The share of a height up to `farthest` that fits in `room` metres: all of it, or
    the room over the farthest."""
    return 1.0 if farthest <= room else room / farthest


class Flock(ParamParticles):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(
                type="color_list", default=list(FLOCK_PALETTE), label="Palette"
            ),
            "count": EffectParam(type="int", default=40, min=5, max=200, step=5, label="Birds"),
            "spread_m": EffectParam(
                type="float",
                default=0.8,
                min=0.2,
                max=3.0,
                step=0.1,
                label="Spread",
                description="Metres from the flock's middle",
            ),
            "scatter": EffectParam(
                type="float",
                default=3.0,
                min=1.0,
                max=8.0,
                step=0.5,
                label="Scatter",
                description="How far the flock scatters, times its spread",
            ),
            "size": EffectParam(
                type="float",
                default=0.2,
                min=0.05,
                max=0.6,
                step=0.05,
                label="Bird size",
                description="Metres",
            ),
        }

    def positions(self, ctx: RenderContext, ground: Ground) -> Particles:
        values = self._values
        trips = ctx.beats / (BEATS_PER_BAR * MOVE_BARS)
        trip = math.floor(trips)
        visits = np.array([trip, trip + 1])
        stops = tour(self._seed, 0, visits, ground.lamps.count)
        here, there = ground.on(stops, draws(self._seed, visits, 1, stream=1)[:, 0])
        share = ease_in_out(trips - trip)
        middle = here + (there - here) * share
        # The band of the lamp it leaves, blended into that of the lamp it comes to.
        floor, ceiling = ground.floor_for(stops), ground.ceiling_for(stops)
        low = floor[0] + (floor[1] - floor[0]) * share
        high = ceiling[0] + (ceiling[1] - ceiling[0]) * share
        u = draws(self._seed, np.arange(int(values["count"])), 4)
        up = 2.0 * u[:, 0] - 1.0
        flat = np.sqrt(1.0 - up * up)
        heading = 2.0 * math.pi * u[:, 1] + 2.0 * math.pi * ctx.beats / (
            BEATS_PER_BAR * SWIRL_BARS
        )
        spread = float(values["spread_m"])
        reach = spread * np.cbrt(u[:, 2])  # spread evenly through a ball
        since = (trips - trip) * BEATS_PER_BAR * MOVE_BARS  # beats since it came to a lamp
        out_by = scattered(since, float(values["scatter"]))
        out = reach * out_by
        # A bird goes up or down FLAT of the way it goes out, but no farther than the room on
        # its side: the farthest any bird goes is scaled to fit, the rest in proportion.
        height = FLAT * out * up
        farthest = FLAT * spread * out_by
        height *= np.where(
            height > 0.0,
            _fit(max(high - middle[2], 0.0), farthest),
            _fit(max(middle[2] - low, 0.0), farthest),
        )
        pos = middle + np.stack(
            [out * flat * np.cos(heading), out * flat * np.sin(heading), height], axis=1
        )
        return swarm(pos, palette_at(self._palette, u[:, 3]), float(values["size"]))
