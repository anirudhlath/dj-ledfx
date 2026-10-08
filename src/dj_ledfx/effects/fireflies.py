"""Fireflies' particles (looks.json "fireflies").

Each firefly wanders on slow waves of its own (particle_tools.wander) round an LED of a lamp
of its own (any of its LEDs), within RANGE_M of it, every lamp taken before any gets two, or
round the anchor they drift toward, within DRIFT_REACH_M; between the floor and the ceiling
either way. It glows at GLOW_LOW of its brightest between flares and flares once in a period
of its own from FLARE_S, so a lamp is lit only while a firefly is near it.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.color import palette_at
from dj_ledfx.effects.params import EffectParam, anchor_param
from dj_ledfx.effects.particle_tools import WANDER_DRAWS, draws, spread_over, swarm, wander
from dj_ledfx.effects.particles import ParamParticles

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.particle_tools import F64, Ground, Particles

FIREFLY_PALETTE = ("#b4ff3c", "#ffe650", "#78ff8c")
RANGE_M = 1.0  # a firefly wanders this far round its LED
DRIFT_REACH_M = 1.5  # drawn to an anchor, they wander within this of it
GLOW_LOW = 0.35  # a firefly's glow between flares, of its brightest
FLARE_S = (2.0, 5.0)  # each flares once a period from this range, its own


class Fireflies(ParamParticles):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(
                type="color_list", default=list(FIREFLY_PALETTE), label="Palette"
            ),
            "count": EffectParam(type="int", default=12, min=1, max=60, step=1, label="Count"),
            "speed": EffectParam(
                type="float",
                default=0.3,
                min=0.05,
                max=2.0,
                step=0.05,
                label="Speed",
                description="Metres a second",
                bindable=True,
            ),
            "glow_size": EffectParam(
                type="float",
                default=0.5,
                min=0.1,
                max=2.0,
                step=0.05,
                label="Glow size",
                description="Metres",
            ),
            "drift_toward": anchor_param("Drift toward", "None: they wander round the lamps"),
        }

    def _boxes(self, ground: Ground, spots: F64) -> tuple[F64, F64]:
        """Where each wanders: round the anchor they drift toward, else round the LED its
        spot (0..1) picks of its lamp."""
        name = str(self._values["drift_toward"])
        anchor = ground.leds.anchors.get(name) if name else None
        if anchor is not None:
            return ground.box(DRIFT_REACH_M, around=anchor)
        lamps = spread_over(self._seed, len(spots), ground.lamps.count)
        return ground.box(RANGE_M, around=ground.on(lamps, spots))

    def positions(self, ctx: RenderContext, ground: Ground) -> Particles:
        values = self._values
        count = int(values["count"])
        u = draws(self._seed, np.arange(count), WANDER_DRAWS + 4)
        shade, period, phase, spot = u[:, WANDER_DRAWS:].T
        low, high = self._boxes(ground, spot)
        where = wander(u[:, :WANDER_DRAWS], ctx.t, float(values["speed"]), low, high)
        period = FLARE_S[0] + (FLARE_S[1] - FLARE_S[0]) * period
        flare = (0.5 - 0.5 * np.cos(2.0 * math.pi * (ctx.t / period + phase))) ** 4
        glow = GLOW_LOW + (1.0 - GLOW_LOW) * flare
        colour = palette_at(self._palette, shade) * glow[:, None].astype(np.float32)
        return swarm(where, colour, float(values["glow_size"]))
