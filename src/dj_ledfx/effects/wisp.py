"""Wisp's particles (looks.json "wisp"): wisps that roam the home room to room.

Each wisp rests on an LED of a lamp for hold_s, then glides over move_s to a lamp in another
room, on a tour of its own (particle_tools.tour) over the rooms that have lamps: every room
once a round, in a shuffled order, never the same room twice running. The lamp it rests on in
a room, and the LED of that lamp, are drawn afresh each visit. With one room, or none on the
map, it tours the lamps instead, as Spotlights does. A wisp's light is the particle's falloff
at `size`, so a lamp glows only while one is near. The wisps start their steps at even shares
of a step apart, so no two set off together. It runs on seconds, not beats.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.easing import ease_in_out
from dj_ledfx.effects.ledset import NO_ROOM
from dj_ledfx.effects.params import EffectParam, level_param
from dj_ledfx.effects.particle_tools import arc, draws, lamp_rooms, swarm, tour
from dj_ledfx.effects.particles import ParamParticles

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.particle_tools import Ground, Particles

WISP_PALETTE = ("#ffe2b8",)  # one warm white
MAX_WISPS = 4  # the most `count` takes; visit n of wisp k draws from key n * MAX_WISPS + k
WISP_VISITS = 1  # the stream the lamps and the LEDs of the visits are drawn from


class Wisp(ParamParticles):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "count": EffectParam(
                type="int", default=2, min=1, max=MAX_WISPS, step=1, label="Wisps"
            ),
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
                max=20.0,
                step=0.5,
                label="Glide",
                description="Seconds from one room to the next",
                bindable=True,
            ),
            "size": EffectParam(
                type="float",
                default=0.5,
                min=0.2,
                max=1.5,
                step=0.1,
                label="Wisp size",
                description="Metres",
            ),
            "palette": EffectParam(type="color_list", default=list(WISP_PALETTE), label="Palette"),
            "level": level_param(0.8),
        }

    def positions(self, ctx: RenderContext, ground: Ground) -> Particles:
        values = self._values
        count = int(values["count"])
        hold, move = float(values["hold_s"]), float(values["move_s"])
        rest = hold / (hold + move)  # the share of each step spent resting
        wisp = np.arange(count)
        clock = ctx.t / (hold + move) + wisp / count
        step = np.floor(clock).astype(np.int64)
        part = clock - step
        visits = np.stack([step, step + 1], axis=1)  # the lamp it rests on, then the next
        keys = (visits * MAX_WISPS + wisp[:, None]).ravel()
        u = draws(self._seed, keys, 2, WISP_VISITS).reshape(count, 2, 2)
        stops = self._stops(ground, wisp[:, None], visits, u[..., 0])
        here, there = np.moveaxis(ground.on(stops, u[..., 1]), 1, 0)
        glide = ease_in_out(np.maximum(0.0, (part - rest) / (1.0 - rest)))
        pos = arc(here, there, glide, 0.0)
        colour = self._palette[wisp % len(self._palette)] * np.float32(values["level"])
        return swarm(pos, colour, float(values["size"]))

    def _stops(
        self,
        ground: Ground,
        wisp: NDArray[np.int64],
        visits: NDArray[np.int64],
        pick: NDArray[np.float64],
    ) -> NDArray[np.intp]:
        """The lamp each wisp rests on at each of its visits: the room's lamp that `pick` (0..1)
        picks, in the room its tour is in at the visit; with fewer than two rooms that have
        lamps, the lamp its tour is at."""
        room = lamp_rooms(ground)
        placed = np.flatnonzero(room != NO_ROOM)  # a lamp in no room is a stop of no room's
        by_room = placed[np.argsort(room[placed], kind="stable")]  # the lamps, room by room
        rooms, first, many = np.unique(room[by_room], return_index=True, return_counts=True)
        if len(rooms) < 2:
            return tour(self._seed, wisp, visits, ground.lamps.count)
        in_room = tour(self._seed, wisp, visits, len(rooms))  # an index into `rooms`
        lamps = many[in_room]
        which = np.minimum((pick * lamps).astype(np.intp), lamps - 1)
        stops: NDArray[np.intp] = by_room[first[in_room] + which]
        return stops
