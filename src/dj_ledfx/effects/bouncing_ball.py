"""Bouncing ball's particles (looks.json "ball").

The ball lands on a lamp on every beat, at its foot under one of its LEDs (Ground.foot, any
of its LEDs, its own each beat), and bounces from there to the next lamp of its tour
(particle_tools.tour: every lamp once a round in a shuffled order, never the same lamp twice
in a row), height_m up over the beat, landing on it on the next beat. It takes the palette's
next colour at each bounce.

A bounce fits under the ceiling instead of flattening against it: it rises height_m, but no
more than fits under the higher ceiling of its two lamps (Ground.ceiling_for, widened to take
in a lamp the map or a layer's transform puts over the ceiling): the most an arc between its
two feet can rise and keep its top at or under it (particle_tools.rise_under), so a bounce
between feet near the top of the band still arcs. That ceiling is the same for a bounce
whichever way it goes, and the bounce before and the bounce after share a foot, so the ball
doesn't jump at the beat. The feet are in their lamps' bands and a bounce only rises over the
line between them, so the floor never binds, and with no room at all (a ceiling under the
feet, which ceiling_for never gives beyond float32 rounding) the ball stays on the line
between them, not under it.

The ball is one particle: the count is 1, whatever the lamps, within MAX_PARTICLES.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.params import EffectParam
from dj_ledfx.effects.particle_tools import arc, draws, rise_under, swarm, tour
from dj_ledfx.effects.particles import ParamParticles

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.particle_tools import Ground, Particles

BALL_PALETTE = ("#ff3c50", "#ffd23c", "#3cff8c", "#3c8cff")


class BouncingBall(ParamParticles):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(type="color_list", default=list(BALL_PALETTE), label="Palette"),
            "height_m": EffectParam(
                type="float",
                default=1.5,
                min=0.3,
                max=3.0,
                step=0.1,
                label="Bounce",
                description="Metres the ball bounces",
                bindable=True,
            ),
            "size": EffectParam(
                type="float",
                default=0.5,
                min=0.1,
                max=1.5,
                step=0.05,
                label="Ball size",
                description="Metres",
            ),
        }

    def positions(self, ctx: RenderContext, ground: Ground) -> Particles:
        values = self._values
        beat = math.floor(ctx.beats)
        bounces = np.array([beat, beat + 1])
        stops = tour(self._seed, 0, bounces, ground.lamps.count)
        here, there = ground.foot(stops, draws(self._seed, bounces, 1, stream=1)[:, 0])
        # Under the higher ceiling of the bounce's two lamps, whichever way it goes.
        height = rise_under(
            ground.ceiling_for(stops).max(), here[2], there[2], float(values["height_m"])
        )
        where = arc(here, there, [ctx.beats - beat], height)
        palette = self._palette
        return swarm(where, palette[beat % len(palette)], float(values["size"]))
