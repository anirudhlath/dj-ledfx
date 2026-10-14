"""Vortex's particles (looks.json "vortex").

Each particle circles the zone's middle on the ring through an LED of one of its lamps (any
of its LEDs, at random; seen from above), the lamps taken in turn, so the particles sweep
through the lamps as they go round, the nearer rings faster. Each rises from the floor to
the ceiling over rise_bars bars, then starts again at the floor. The turn follows the music,
not the clock: `kick` of each beat's share of the turn comes in a rush at the beat.

The rise reaches every lamp: its band is the zone's floor and ceiling, widened to take in
all of the lamps' LEDs where the map (or a layer's transform) puts a lamp under the floor or
over the ceiling (rise_band). The count is the `count` setting, at most 300 and so within
MAX_PARTICLES, whatever the number of lamps: each particle takes a lamp in turn and shares
nothing out.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.color import palette_at
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.effects.particle_tools import draws, swarm
from dj_ledfx.effects.particles import ParamParticles
from dj_ledfx.tempo.model import BEATS_PER_BAR

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.particle_tools import Ground, Particles

VORTEX_PALETTE = ("#7828ff", "#2878ff", "#28e6c8")  # low to high
LEAST_RADIUS_M = 0.5  # the vortex is at least this wide each way
JITTER_M = 0.2  # a particle circles this close to its lamp's ring, either side


def rise_band(ground: Ground) -> tuple[float, float]:
    """The heights the rise runs between: the zone's floor and ceiling, widened to take in
    every lamp's LEDs. Decided in float32, as the LEDs are held (Ground.floor_for and
    ceiling_for): a lamp inside the band, one at its edge included, leaves the zone's own
    floor and ceiling as they are, to the last bit."""
    stops = np.arange(ground.lamps.count)
    return float(ground.floor_for(stops).min()), float(ground.ceiling_for(stops).max())


def kicked(beats: float, kick: float) -> float:
    """The beats counted with `kick` of each beat in a rush at its start: whole beats stay
    whole, and the share of a beat gone is eased out (fast, then slow) as much as kick says."""
    whole = math.floor(beats)
    part = beats - whole
    return whole + (1.0 - kick) * part + kick * (1.0 - (1.0 - part) ** 3)


class Vortex(ParamParticles):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(
                type="color_list", default=list(VORTEX_PALETTE), label="Palette"
            ),
            "count": EffectParam(
                type="int", default=60, min=10, max=300, step=10, label="Particles"
            ),
            "turns_per_bar": EffectParam(
                type="float",
                default=0.5,
                min=0.1,
                max=2.0,
                step=0.1,
                label="Spin",
                description="Turns round the room each bar",
                bindable=True,
            ),
            "kick": EffectParam(
                type="float",
                default=0.7,
                min=0.0,
                max=1.0,
                step=0.05,
                label="Kick",
                description="How much of each beat's turn comes at the beat",
            ),
            "rise_bars": EffectParam(
                type="float",
                default=4.0,
                min=1.0,
                max=16.0,
                step=1.0,
                label="Rise",
                description="Bars from the floor to the ceiling",
            ),
            "size": EffectParam(
                type="float",
                default=0.3,
                min=0.1,
                max=1.0,
                step=0.05,
                label="Particle size",
                description="Metres",
            ),
        }

    def positions(self, ctx: RenderContext, ground: Ground) -> Particles:
        values = self._values
        count = int(values["count"])
        u = draws(self._seed, np.arange(count), 4)
        bars = kicked(ctx.beats, float(values["kick"])) / BEATS_PER_BAR
        lamps = ground.lamps
        middle = ((ground.low + ground.high) / 2.0).astype(np.float64)
        past = ground.on(np.arange(count) % lamps.count, u[:, 3])
        ring = np.linalg.norm(past[:, :2] - middle[:2], axis=1)
        out = np.maximum(ring + JITTER_M * (2.0 * u[:, 0] - 1.0), 0.0)
        widest = max(float(out.max()), LEAST_RADIUS_M)
        speed = float(values["turns_per_bar"]) * (1.4 - 0.6 * out / widest)  # nearer: faster
        turn = 2.0 * math.pi * (u[:, 1] + bars * speed)
        height = np.mod(u[:, 2] + bars / float(values["rise_bars"]), 1.0)
        floor, ceiling = rise_band(ground)
        pos = np.stack(
            [
                middle[0] + out * np.cos(turn),
                middle[1] + out * np.sin(turn),
                floor + height * (ceiling - floor),
            ],
            axis=1,
        )
        glow = np.sin(math.pi * height)  # dark at the floor and at the ceiling
        colour = palette_at(self._palette, height) * glow[:, None].astype(np.float32)
        return swarm(pos, colour, float(values["size"]))
