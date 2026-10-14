"""Spotlights' particles (looks.json "spotlights").

Each spotlight rests on a lamp for hold_s, on an LED of it (any of its LEDs, its own each
visit), then glides to the next over move_s, on a tour of its own (particle_tools.tour):
every lamp once a round in a shuffled order, never the same lamp twice in a row. The
spotlights start their steps at even shares of a step apart, so no two set off together (and
with a rest shorter than the glide, each is on the move most of the time).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.easing import ease_in_out
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.effects.particle_tools import draws, swarm, tour
from dj_ledfx.effects.particles import ParamParticles

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.particle_tools import Ground, Particles

SPOT_PALETTE = ("#ffd28c", "#8cc8ff")


class Spotlights(ParamParticles):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(type="color_list", default=list(SPOT_PALETTE), label="Palette"),
            "count": EffectParam(type="int", default=2, min=1, max=6, step=1, label="Spotlights"),
            "hold_s": EffectParam(
                type="float",
                default=4.0,
                min=0.5,
                max=30.0,
                step=0.5,
                label="Rest",
                description="Seconds on each lamp",
                bindable=True,
            ),
            "move_s": EffectParam(
                type="float",
                default=3.0,
                min=0.5,
                max=30.0,
                step=0.5,
                label="Glide",
                description="Seconds from one lamp to the next",
                bindable=True,
            ),
            "size": EffectParam(
                type="float",
                default=0.8,
                min=0.2,
                max=3.0,
                step=0.1,
                label="Spot size",
                description="Metres",
            ),
        }

    def positions(self, ctx: RenderContext, ground: Ground) -> Particles:
        values = self._values
        count = int(values["count"])
        hold, move = float(values["hold_s"]), float(values["move_s"])
        rest = hold / (hold + move)  # the share of each step spent resting
        spot = np.arange(count)
        clock = ctx.t / (hold + move) + spot / count
        step = np.floor(clock).astype(np.int64)
        part = clock - step
        visits = np.stack([step, step + 1], axis=1)  # the lamp it rests on, then the next
        stops = tour(self._seed, spot[:, None], visits, ground.lamps.count)
        picks = draws(self._seed, visits.ravel(), 1, stream=np.repeat(1 + spot, 2))[:, 0]
        here, there = np.moveaxis(ground.on(stops, picks.reshape(count, 2)), 1, 0)
        glide = ease_in_out(np.maximum(0.0, (part - rest) / (1.0 - rest)))
        pos = here + (there - here) * glide[:, None]
        colour = self._palette[np.arange(count) % len(self._palette)]
        return swarm(pos, colour, float(values["size"]))
