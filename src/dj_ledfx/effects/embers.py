"""Embers' particles (looks.json "embers"); the look's firmware layer runs LIFX Flame beside
them.

Each lamp sends embers up from its foot (spec §5.1: "embers rise from lamp bases"), a few at
a time, each under an LED of its own (Ground.foot), so a long light smoulders along its
length; each climbs to just over the lamp's top as it dies: hot and bright as it catches,
dimmer and redder as it climbs, flickering all the way. Ember n of lamp s comes from draws()
of its key alone, so an ember is where it is whenever it's drawn.

A home with so many lamps that the embers would pass MAX_PARTICLES makes fewer of them
(lamp_streams): every lamp's rate comes down together, so that none is ever cut mid-life.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.color import palette_at
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.effects.particle_tools import LAMP_KEYS, draws, lamp_streams, recent, swarm
from dj_ledfx.effects.particles import MAX_PARTICLES, ParamParticles

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.particle_tools import Ground, Particles

EMBER_PALETTE = ("#fff0a0", "#ffa020", "#ff4808", "#901000")  # catching to dying
CLIMB_OVER_M = 0.3  # an ember dies this far over its lamp's top (or at the ceiling)
WOBBLE_M = 0.06  # how far it wanders from its LED as it climbs
WOBBLE_S = 2.0  # once round in this long
LIFE_SPREAD = 0.5  # an ember lives its rise time, give or take a quarter
LONGEST = 1.0 + LIFE_SPREAD / 2.0  # the longest life, in rise times
FLICKER_HZ = 7.0
CATCH_S = 0.15  # it brightens over this as it catches


class Embers(ParamParticles):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(
                type="color_list", default=list(EMBER_PALETTE), label="Palette"
            ),
            "per_lamp": EffectParam(
                type="float",
                default=3.0,
                min=0.5,
                max=10.0,
                step=0.5,
                label="Embers",
                description="Embers climbing each lamp at once",
                bindable=True,
            ),
            "rise_s": EffectParam(
                type="float",
                default=4.0,
                min=1.0,
                max=15.0,
                step=0.5,
                label="Rise",
                description="Seconds an ember takes to climb",
            ),
            "size": EffectParam(
                type="float",
                default=0.12,
                min=0.03,
                max=0.5,
                step=0.01,
                label="Ember size",
                description="Metres",
            ),
        }

    def positions(self, ctx: RenderContext, ground: Ground) -> Particles:
        values = self._values
        lamps = ground.lamps
        rise = float(values["rise_s"])
        streams = lamp_streams(
            self._seed, lamps.count, float(values["per_lamp"]), LONGEST, MAX_PARTICLES
        )
        every = rise / streams.rate  # one ember leaves each lamp this often
        n = recent(ctx.t, every, rise * LONGEST)
        event, lamp = streams.events(n)  # ember n of lamp s draws from key n * LAMP_KEYS + s
        u = draws(self._seed, event * LAMP_KEYS + lamp, 5)
        born = streams.born(event, lamp, u[:, 0]) * every
        age = ctx.t - born
        share = age / (rise * (1.0 - LIFE_SPREAD / 2.0 + LIFE_SPREAD * u[:, 1]))
        alive = np.flatnonzero((age >= 0.0) & (share < 1.0))
        alive = alive[np.argsort(born[alive], kind="stable")]  # oldest first
        lamp, u, age, share = lamp[alive], u[alive], age[alive], share[alive]
        wobble = 2.0 * math.pi * (u[:, 2] + age / WOBBLE_S)
        foot = ground.foot(lamp, u[:, 4])
        top = np.maximum(np.minimum(lamps.high[lamp] + CLIMB_OVER_M, ground.ceiling), foot[:, 2])
        pos = np.stack(
            [
                foot[:, 0] + WOBBLE_M * np.sin(wobble),
                foot[:, 1] + WOBBLE_M * np.cos(wobble),
                foot[:, 2] + (top - foot[:, 2]) * share**0.8,
            ],
            axis=1,
        )
        flicker = 0.75 + 0.25 * np.sin(2.0 * math.pi * (FLICKER_HZ * age + u[:, 3]))
        glow = flicker * (1.0 - share) * np.minimum(1.0, age / CATCH_S)
        colour = palette_at(self._palette, share) * glow[:, None].astype(np.float32)
        return swarm(pos, colour, float(values["size"]))
