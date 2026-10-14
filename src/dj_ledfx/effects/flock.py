"""Flock's particles (looks.json "flock").

The flock flies from lamp to lamp on a tour (particle_tools.tour), MOVE_BARS bars from one
to the next, easing in and out, so it gathers on each lamp in turn, round an LED of it (any
of its LEDs, its own each visit). Each bird keeps its own place in the flock, within
spread_m of its middle, and the whole flock turns about its middle once every SWIRL_BARS
bars. On the downbeat of every other bar, as the flock comes to a lamp, the birds burst out
to `scatter` times their places and gather again over the next few beats (`scattered`).

Heights: the birds keep between the floor and the ceiling, widened to take in the lamp's own
LEDs where the map (or a layer's transform) puts a lamp outside them (Ground.floor_for and
ceiling_for). The flock is FLAT flatter than it is wide, so the farthest a bird goes up or
down from its middle is FLAT of the spread, scattered. It gives way to the band rather than
being flattened against it (`_gives_way`): its vertical centre stays round its LED wherever
the flock's height fits in the band round it, and where an edge is too near the whole flock
moves in from that edge, by the shortfall and no more, so a flock gathered on the floor
stands on it, and one on the ceiling hangs from it, with its shape kept and no sheet of birds
level with the edge. Only a band less high than the flock's whole height scales it, about the
band's middle, until its farthest bird comes just to the edges (so a lone bulb with no map,
whose band is half a metre, has the flock fill that). The band is the one between its two
lamps' bands that the flock moves through with its middle, so it is its lamp's own band
wherever the flock gathers and stays inside the union of the two on the way. The flock's
middle, the band and `scattered` (1 at both ends of a move) are continuous at the downbeat,
and so the way the flock gives way is; a jump in any of them would pop the birds' heights
there.

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
from dj_ledfx.effects.particle_tools import draws, in_ball, swarm, tour
from dj_ledfx.effects.particles import ParamParticles
from dj_ledfx.tempo.model import BEATS_PER_BAR

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.particle_tools import Ground, Particles

FLOCK_PALETTE = ("#fff0c8", "#ffb464", "#ff6482")
MOVE_BARS = 2  # the flock takes this many bars from one lamp to the next
MOVE_BEATS = BEATS_PER_BAR * MOVE_BARS
SWIRL_BARS = 2.0  # it turns once in this many bars
SCATTER_BEATS = 0.75  # a scatter is widest this many beats after its downbeat
FLAT = 0.5  # a flock is this much flatter than it is wide


def scattered(since: float, scatter: float) -> float:
    """How far out the birds are, as a share of their places, `since` beats after the
    downbeat that scatters them: 1 on the downbeat, out to `scatter` at SCATTER_BEATS, then
    back, and exactly 1 again at MOVE_BEATS, where the next move opens (a curve that merely
    came near 1 there would pop the birds out by the difference on the downbeat)."""
    rise = since / SCATTER_BEATS
    last = math.exp(1.0 - MOVE_BEATS / SCATTER_BEATS)  # exp(1 - rise) when the move ends
    bump = rise * (math.exp(1.0 - rise) - last) / (1.0 - last)
    return 1.0 + (scatter - 1.0) * bump


def _gives_way(middle: float, low: float, high: float, farthest: float) -> tuple[float, float]:
    """Where a flock round `middle`, whose farthest bird goes `farthest` metres up or down,
    puts its vertical centre, and the share of its heights it keeps, to stay between `low` and
    `high`. It gives way to an edge instead of lying along it: where the band round `middle`
    holds the flock's whole height its centre stays at `middle` (share 1), and where an edge is
    nearer than `farthest` the centre moves in from it by the shortfall. Only a band less high
    than the flock's whole height (twice `farthest`) scales it, to the share that brings its
    farthest bird just to the edges, about the band's middle. A band of no height, or less
    than none (which Ground never gives), puts every bird at one height."""
    half = max(high - low, 0.0) / 2.0
    fit = 1.0 if farthest <= half else half / farthest
    reach = fit * farthest
    return min(max(middle, low + reach), high - reach), fit


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
        trips = ctx.beats / MOVE_BEATS
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
        spread = float(values["spread_m"])
        since = (trips - trip) * MOVE_BEATS  # beats since it came to a lamp
        out_by = scattered(since, float(values["scatter"]))
        # The birds' places in a ball of spread_m, scattered, turning with the flock.
        turn = u[:, 1] + ctx.beats / (BEATS_PER_BAR * SWIRL_BARS)
        ball = in_ball(u[:, 0], turn, u[:, 2], spread * out_by)
        # A bird goes up or down FLAT of the way it goes out; the flock gives way to the band.
        centre, fit = _gives_way(float(middle[2]), float(low), float(high), FLAT * spread * out_by)
        pos = np.stack(
            [middle[0] + ball[:, 0], middle[1] + ball[:, 1], centre + fit * FLAT * ball[:, 2]],
            axis=1,
        )
        return swarm(pos, palette_at(self._palette, u[:, 3]), float(values["size"]))
