"""Beat bursts' particles (looks.json "bursts").

Beat j's burst leaves the anchor on the beat (the middle of the zone when none is set, or the
map has no such anchor), a bigger one on the downbeat, each particle flying out to an LED of a
lamp of its own (any lamp and any of its LEDs, at random) and slowing as it lands there,
ARRIVE of the way through its fade, then fading on the lamp; all of it is gone fade_beats after
the beat. Its colour is the palette's colour j, round and round. Ages are in beats, so a burst
keeps its shape at any tempo.

A particle lands within SCATTER_M of its LED, but no lower than the floor or the lamp's lowest
LED and no higher than the ceiling or the lamp's top (Ground.floor_for and ceiling_for): the
scatter is an overhang, and an overhang stops at the floor and the ceiling.

At most ceil(fade_beats) bursts are in the air at once, whatever the tempo and however many
lamps there are (a particle's lamp is drawn, not dealt out): at the largest settings 3 * 30 +
120 = 210 particles, one downbeat's burst among them. So the effect keeps to MAX_PARTICLES
itself, and step() never cuts a burst short.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.field_tools import anchor_or_centre
from dj_ledfx.effects.params import EffectParam, anchor_param
from dj_ledfx.effects.particle_tools import draws, fired, swarm
from dj_ledfx.effects.particles import ParamParticles
from dj_ledfx.tempo.model import BEATS_PER_BAR

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.particle_tools import Ground, Particles

BURST_PALETTE = ("#ff3cc8", "#3cc8ff", "#ffe63c", "#ffffff")
ARRIVE = 0.4  # a particle lands on its lamp this share of the way through its fade
SCATTER_M = 0.15  # it lands within this of its LED
BEAT_KEYS = 1024  # particle k of beat j's burst draws from key j * BEAT_KEYS + k


class BeatBursts(ParamParticles):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "anchor": anchor_param("Fires from"),
            "palette": EffectParam(
                type="color_list", default=list(BURST_PALETTE), label="Palette"
            ),
            "per_beat": EffectParam(
                type="int",
                default=12,
                min=1,
                max=30,
                step=1,
                label="Particles",
                description="Particles in each beat's burst",
                bindable=True,
            ),
            "downbeat": EffectParam(
                type="float",
                default=2.5,
                min=1.0,
                max=4.0,
                step=0.5,
                label="Downbeat",
                description="Times as many on the downbeat",
            ),
            "fade_beats": EffectParam(
                type="float",
                default=1.5,
                min=0.25,
                max=4.0,
                step=0.25,
                label="Fade",
                description="Beats a burst takes to fade",
            ),
            "size": EffectParam(
                type="float",
                default=0.25,
                min=0.05,
                max=1.0,
                step=0.05,
                label="Particle size",
                description="Metres",
            ),
        }

    def burst_size(self, beat: int) -> int:
        """How many particles beat `beat`'s burst fires."""
        return int(self._sizes(np.int64(beat)))

    def _sizes(self, beats: NDArray[np.int64] | np.int64) -> NDArray[np.int64]:
        """How many particles each of these beats' bursts fires: a downbeat's is bigger."""
        size = int(self._values["per_beat"])
        big = round(size * float(self._values["downbeat"]))
        sizes: NDArray[np.int64] = np.where(beats % BEATS_PER_BAR == 0, big, size)
        return sizes

    def positions(self, ctx: RenderContext, ground: Ground) -> Particles:
        values = self._values
        fade = float(values["fade_beats"])
        beats = ctx.beats
        alive = fired(beats, fade)
        sizes = self._sizes(alive)
        beat = np.repeat(alive, sizes)
        k = np.arange(len(beat)) - np.repeat(np.cumsum(sizes) - sizes, sizes)  # 0, 1, … in a burst
        u = draws(self._seed, beat * BEAT_KEYS + k, 5)
        lamp = ground.lamps.pick(u[:, 0])
        up = 2.0 * u[:, 1] - 1.0  # where round its LED it lands
        side = 2.0 * math.pi * u[:, 2]
        flat = np.sqrt(1.0 - up * up)
        near = SCATTER_M * np.cbrt(u[:, 3])[:, None]
        landing = ground.on(lamp, u[:, 4]) + near * np.stack(
            [flat * np.cos(side), flat * np.sin(side), up], axis=1
        )
        # The scatter is an overhang: it stops at the floor and the ceiling, but never short
        # of the lamp's own LEDs.
        landing[:, 2] = ground.within(lamp, landing[:, 2])
        age = (beats - beat) / fade  # 0 on the beat, 1 faded
        way = 1.0 - (1.0 - np.minimum(age / ARRIVE, 1.0)) ** 2  # fast out, slowing to land
        origin = anchor_or_centre(ground.leds, str(values["anchor"])).astype(np.float64)
        pos = origin + (landing - origin) * way[:, None]
        palette = self._palette
        colour = palette[beat % len(palette)] * (1.0 - age)[:, None].astype(np.float32)
        return swarm(pos, colour, float(values["size"]))
