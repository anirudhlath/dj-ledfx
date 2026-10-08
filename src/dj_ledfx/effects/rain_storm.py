"""Rain storm's particles (looks.json "rain"): drops and lightning.

Drops run down each lamp from just over its top to just under its bottom, a few at a time,
each past an LED of its own (Ground.on), so rain runs along a long light's length. A strike
comes once in each stretch of 60 / strikes_per_min seconds, at a random moment and a random
spot over the zone's floor at half the ceiling's height: one particle as wide as
strike_reach, so each lamp lights by its distance from the strike. It flashes, dims, and
flickers once more.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.color import palette_at, palette_float
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.effects.particle_tools import NO_PARTICLES, draws, joined, recent, swarm
from dj_ledfx.effects.particles import ParamParticles

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.particle_tools import Ground, Particles

RAIN_PALETTE = ("#2850ff", "#78b4ff", "#c8e6ff")
LIGHTNING = "#e6eeff"
OVER_M = 0.25  # a drop starts this far over its lamp's top
UNDER_M = 0.15  # and runs out this far under its bottom
JITTER_M = 0.05  # how far from its LED a drop runs
EDGE = 0.1  # a drop fades in over this share of its run, and out over the last
FLASH_S = 0.6  # a strike is over in this long
LAMP_KEYS = 65536  # drop n of lamp s draws from key n * LAMP_KEYS + s


def flash(age: NDArray[np.float64]) -> NDArray[np.float64]:
    """A strike's brightness `age` seconds after it: a flash, and a flicker after it."""
    envelope: NDArray[np.float64] = np.exp(-age / 0.08) + 0.6 * np.exp(
        -(((age - 0.25) / 0.06) ** 2)
    )
    return np.minimum(envelope, 1.0)


class RainStorm(ParamParticles):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(type="color_list", default=list(RAIN_PALETTE), label="Palette"),
            "lightning": EffectParam(type="color", default=LIGHTNING, label="Lightning"),
            "drops_per_lamp": EffectParam(
                type="float",
                default=2.0,
                min=0.5,
                max=8.0,
                step=0.5,
                label="Drops",
                description="Drops running down each lamp at once",
                bindable=True,
            ),
            "fall_s": EffectParam(
                type="float",
                default=1.0,
                min=0.3,
                max=4.0,
                step=0.1,
                label="Fall",
                description="Seconds a drop takes to run down a lamp",
            ),
            "size": EffectParam(
                type="float",
                default=0.1,
                min=0.03,
                max=0.4,
                step=0.01,
                label="Drop size",
                description="Metres",
            ),
            "strikes_per_min": EffectParam(
                type="float",
                default=4.0,
                min=0.0,
                max=30.0,
                step=1.0,
                label="Lightning",
                description="Strikes a minute; none at 0",
                bindable=True,
            ),
            "strike_reach": EffectParam(
                type="float",
                default=3.0,
                min=1.0,
                max=10.0,
                step=0.5,
                label="Strike reach",
                description="Metres",
            ),
        }

    def _prepare(self) -> None:
        super()._prepare()
        self._lightning = palette_float([self._values["lightning"]])[0]

    def positions(self, ctx: RenderContext, ground: Ground) -> Particles:
        return joined(self._drops(ctx, ground), self._strikes(ctx, ground))

    def _drops(self, ctx: RenderContext, ground: Ground) -> Particles:
        values = self._values
        lamps = ground.lamps
        fall = float(values["fall_s"])
        every = fall / float(values["drops_per_lamp"])  # a drop starts down each lamp this often
        n = recent(ctx.t, every, fall)
        lamp = np.tile(np.arange(lamps.count), len(n))
        u = draws(self._seed, np.repeat(n, lamps.count) * LAMP_KEYS + lamp, 4)
        born = (np.repeat(n, lamps.count) + u[:, 0]) * every
        share = (ctx.t - born) / fall  # 0 over the lamp's top, 1 under its bottom
        alive = np.flatnonzero((share >= 0.0) & (share < 1.0))
        alive = alive[np.argsort(born[alive], kind="stable")]  # oldest first
        lamp, u, share = lamp[alive], u[alive], share[alive]
        top, bottom = lamps.high[lamp] + OVER_M, lamps.low[lamp] - UNDER_M
        side = 2.0 * math.pi * u[:, 1]
        past = ground.on(lamp, u[:, 3])
        pos = np.stack(
            [
                past[:, 0] + JITTER_M * np.cos(side),
                past[:, 1] + JITTER_M * np.sin(side),
                top - (top - bottom) * share,
            ],
            axis=1,
        )
        fade = np.minimum(1.0, np.minimum(share, 1.0 - share) / EDGE)
        colour = palette_at(self._palette, u[:, 2]) * fade[:, None].astype(np.float32)
        return swarm(pos, colour, float(values["size"]))

    def _strikes(self, ctx: RenderContext, ground: Ground) -> Particles:
        per_min = float(self._values["strikes_per_min"])
        if per_min <= 0.0:
            return NO_PARTICLES
        every = 60.0 / per_min
        n = recent(ctx.t, every, FLASH_S)
        u = draws(self._seed, n, 3, stream=1)
        age = ctx.t - (n + u[:, 0]) * every
        alive = (age >= 0.0) & (age < FLASH_S)
        low, high = ground.low.astype(np.float64), ground.high.astype(np.float64)
        spot = low[:2] + u[alive, 1:] * (high[:2] - low[:2])
        pos = np.column_stack([spot, np.full(len(spot), (ground.floor + ground.ceiling) / 2.0)])
        colour = self._lightning[None, :] * flash(age[alive])[:, None].astype(np.float32)
        return swarm(pos, colour, float(self._values["strike_reach"]))
