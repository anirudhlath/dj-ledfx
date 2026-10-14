"""Twin comets' particles (looks.json "comets").

The comets go round the zone's lamps in a loop (their order round its middle, seen from
above), one lamp a beat: each leaves a lamp on the beat, hops through the air to the next
and lands on it, on an LED of it (any of its LEDs, its own each visit), on the next beat.
They start on opposite sides of the loop, so they chase each other round it. Each trails a
tail of fading, shrinking particles where it was over the last tail_beats.

A hop rises HOP of the way it goes over the line between its two LEDs, but no more than
fits under the higher ceiling of its two lamps (Ground.ceiling_for, widened to take in a
lamp the map or a layer's transform puts over the ceiling): the most an arc between them can
rise and keep its top at or under it (particle_tools.rise_under). So it fits under the
ceiling instead of flattening against it, and still arcs to an LED near the top of the band.
The line itself, and the hop above it, stay between the two LEDs, so the floor never binds,
and with no room at all (a ceiling under the LEDs, which ceiling_for never gives beyond
float32 rounding) the hop stays on the line, not under it. Both lamps' band is the same for
a hop whichever way it goes, and every hop starts where the one before landed, so a comet
doesn't jump at the beat.

Both comets and all their tails are worked out at once, as one array, and listed together
oldest first (particle_tools.in_birth_order, by the beat each was left behind at): the tails'
ends, one of each comet, to the two heads. The count is COMETS * (tail + 1), at most 2 * 31 =
62 at the largest settings whatever the lamps, so the effect keeps to MAX_PARTICLES itself
and step() never cuts a particle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.easing import ease_in_out
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.effects.particle_tools import (
    arc,
    around,
    draws,
    in_birth_order,
    rise_under,
    swarm,
)
from dj_ledfx.effects.particles import ParamParticles

if TYPE_CHECKING:
    from numpy.typing import ArrayLike, NDArray

    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.particle_tools import Ground, Particles

COMET_PALETTE = ("#ff6428", "#28c8ff")
COMETS = 2
HOP = 0.25  # a hop rises this share of the way it goes


class TwinComets(ParamParticles):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(
                type="color_list", default=list(COMET_PALETTE), label="Palette"
            ),
            "tail": EffectParam(
                type="int",
                default=8,
                min=0,
                max=30,
                step=1,
                label="Tail",
                description="Particles in each comet's tail",
            ),
            "tail_beats": EffectParam(
                type="float",
                default=0.5,
                min=0.1,
                max=2.0,
                step=0.1,
                label="Tail length",
                description="Beats each tail reaches back",
            ),
            "size": EffectParam(
                type="float",
                default=0.35,
                min=0.1,
                max=1.0,
                step=0.05,
                label="Comet size",
                description="Metres",
            ),
        }

    def at(
        self, beats: NDArray[np.float64], comet: ArrayLike, ground: Ground
    ) -> NDArray[np.float64]:
        """Where comet `comet` is at each of these beats, shape (…, 3). Beats and comets
        (0 or 1) broadcast, so several comets at several beats are one call."""
        beat, which = np.broadcast_arrays(
            np.asarray(beats, dtype=np.float64), np.asarray(comet, dtype=np.int64)
        )
        loop = around(ground.lamps.centre, ground.centre)
        stops = len(loop)
        start = int(draws(self._seed, [0], 1)[0, 0] * stops)
        whole = np.floor(beat)
        leaves = whole.astype(np.int64) + start + which * (stops // COMETS)
        visit = np.stack([leaves, leaves + 1])  # (2, …): the visit it leaves, the visit it lands
        lamp = loop[visit % stops]
        # A visit's LED is drawn from the visit alone, so a landing is the next hop's start.
        spot = draws(self._seed, visit, 1, stream=np.broadcast_to(1 + which, visit.shape))
        here, there = ground.on(lamp, spot[:, 0].reshape(visit.shape))
        # Under the higher ceiling of the hop's two lamps, whichever way it goes.
        rise = rise_under(
            ground.ceiling_for(lamp).max(axis=0),
            here[..., 2],
            there[..., 2],
            HOP * np.linalg.norm(there - here, axis=-1),
        )
        where = arc(
            here.reshape(-1, 3),
            there.reshape(-1, 3),
            ease_in_out(beat - whole).ravel(),
            rise.ravel(),
        )
        return where.reshape(*beat.shape, 3)

    def positions(self, ctx: RenderContext, ground: Ground) -> Particles:
        values = self._values
        tail = int(values["tail"])
        back = np.arange(tail, -1, -1) / (tail + 1)  # the tail's end first, the head last
        beats = ctx.beats - float(values["tail_beats"]) * back
        comet = np.arange(COMETS)
        pos = self.at(beats, comet[:, None], ground)  # (comets, tail + 1, 3)
        glow = ((1.0 - back) ** 2).astype(np.float32)
        palette = self._palette
        colour = palette[comet % len(palette)][:, None, :] * glow[None, :, None]
        size = float(values["size"]) * (1.0 - 0.6 * back)
        # Each particle's birth is the beat its comet was at its place. Both comets keep the
        # one clock, so the order by beats is the order by seconds at any tempo.
        born = np.broadcast_to(beats, pos.shape[:2]).ravel()
        both = swarm(pos.reshape(-1, 3), colour.reshape(-1, 3), np.tile(size, COMETS))
        return in_birth_order((both, born))
