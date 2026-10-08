"""Snow's particles (looks.json "snow").

Flakes fall past the lamps, per_lamp of them at once for each: each falls from the ceiling
to the floor over its own fall, swaying as it goes, within COLUMN_M of an LED of a lamp
(Ground.on), then starts again at the ceiling over another. Flake i's fall c is where
draws() of that fall says. A flake fades in at the ceiling and out at the floor, and lights
a lamp as it passes.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.color import palette_at
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.effects.particle_tools import draws, swarm
from dj_ledfx.effects.particles import MAX_PARTICLES, ParamParticles

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.particle_tools import Ground, Particles

SNOW_PALETTE = ("#ffffff", "#d2e6ff", "#a0c8ff")
COLUMN_M = 0.3  # a flake falls within this of its LED, seen from above
SWAYS = 2.0  # a flake sways from side to side this many times on its way down
EDGE = 0.05  # it fades in over this share of its fall, and out over the last
FALLS = 4096  # flake i's fall c draws from key c * FALLS + i


class Snowfall(ParamParticles):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(type="color_list", default=list(SNOW_PALETTE), label="Palette"),
            "per_lamp": EffectParam(
                type="float",
                default=4.0,
                min=1.0,
                max=20.0,
                step=1.0,
                label="Snow",
                description="Flakes falling past each lamp at once",
                bindable=True,
            ),
            "fall_s": EffectParam(
                type="float",
                default=12.0,
                min=3.0,
                max=40.0,
                step=1.0,
                label="Fall",
                description="Seconds from the ceiling to the floor",
            ),
            "drift": EffectParam(
                type="float",
                default=0.3,
                min=0.0,
                max=1.5,
                step=0.05,
                label="Drift",
                description="Metres a flake sways to each side",
            ),
            "size": EffectParam(
                type="float",
                default=0.2,
                min=0.05,
                max=0.6,
                step=0.05,
                label="Flake size",
                description="Metres",
            ),
        }

    def positions(self, ctx: RenderContext, ground: Ground) -> Particles:
        values = self._values
        lamps = ground.lamps
        count = min(MAX_PARTICLES, max(1, round(float(values["per_lamp"]) * lamps.count)))
        flakes = np.arange(count)
        own = draws(self._seed, flakes, 3)  # each flake's pace, start and colour
        fall = float(values["fall_s"]) * (0.85 + 0.3 * own[:, 0])
        progress = ctx.t / fall + own[:, 1]
        falls = np.floor(progress).astype(np.int64)
        share = progress - falls  # 0 at the ceiling, 1 at the floor
        where = draws(self._seed, falls * FALLS + flakes, 5, stream=1)  # this fall's place
        past = ground.on(lamps.pick(where[:, 0]), where[:, 4])
        out, side = COLUMN_M * np.sqrt(where[:, 1]), 2.0 * math.pi * where[:, 2]
        turn = 2.0 * math.pi * (SWAYS * share + where[:, 3])
        drift = float(values["drift"])
        pos = np.stack(
            [
                past[:, 0] + out * np.cos(side) + drift * np.sin(turn),
                past[:, 1] + out * np.sin(side) + drift * np.cos(turn),
                ground.ceiling - share * (ground.ceiling - ground.floor),
            ],
            axis=1,
        )
        fade = np.minimum(1.0, np.minimum(share, 1.0 - share) / EDGE)
        colour = palette_at(self._palette, own[:, 2]) * fade[:, None].astype(np.float32)
        return swarm(pos, colour, float(values["size"]))
