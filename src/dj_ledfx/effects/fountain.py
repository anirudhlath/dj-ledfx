"""Fountain's particles (looks.json "fountain").

A steady spray leaves the anchor (the middle of the zone when none is set, or the map has no
such anchor) `rate` times a second, each drop thrown up to about height_m and out on its own
heading, landing back at the anchor's height up to spread_m away, then falling on to the
floor. On every beat a burst of `burst` drops is thrown higher, each to an LED of a lamp of
its own (any lamp and any of its LEDs, at random): it lands there on the next beat and fades
over half a beat. The spray is timed in seconds and the bursts in beats; the drops of both are
listed together, oldest first.

Heights: the spray is the anchor's, so it keeps the zone's band, the floor to the ceiling (it
is gone at the floor); a burst goes to a lamp, so it keeps that lamp's, widened to take in the
lamp's own LEDs where the map (or a layer's transform) puts the lamp outside the zone's
(Ground.floor_for and ceiling_for). Arcs fit under the ceiling rather than flatten against it:
the spray is thrown no higher than the room over the anchor (but LEAST_RISE_M at the least, so
that a drop still has a flight to be timed by) and a burst rises no more than fits under its
lamp's ceiling, the most an arc between its two ends can rise and keep its top at or under it
(particle_tools.rise_under). The spread is the same however short the flight: a drop lands the
spread away at the anchor's height. The clip to the band stays only as the backstop for an
anchor outside it (Ground.within).

The count keeps to MAX_PARTICLES itself, so that step() never cuts a drop short: two beats'
bursts are in the air at the most (BURSTS_ALIVE), and the spray has the rest of the room. A
drop is in the air for `longest` seconds at the most, so at most ceil(rate * longest) + 1 are,
and a rate that would pass the room comes down to fill it. That takes an anchor far over the
ceiling: at the largest settings in a 3 m room, a drop is in the air for 1.56 s at the longest
(thrown from the floor up to the ceiling), so 189 spray drops and 2 * 60 burst drops make 309;
for an anchor 100 m up a drop takes 4.6 s to fall, and the rate comes down to 82 a second.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.color import palette_at
from dj_ledfx.effects.field_tools import anchor_or_centre
from dj_ledfx.effects.params import EffectParam, anchor_param
from dj_ledfx.effects.particle_tools import (
    arc,
    draws,
    fired,
    in_birth_order,
    recent,
    rise_under,
    swarm,
)
from dj_ledfx.effects.particles import MAX_PARTICLES, ParamParticles

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.particle_tools import F64, Ground, Particles

FOUNTAIN_PALETTE = ("#2878ff", "#64c8ff", "#e6faff")
GRAVITY = 9.81  # m/s²
BURST_UP = 1.2  # a burst's drops rise this much higher than the spray, give or take a fifth
LEAST_RISE_M = 0.05  # the spray is thrown at least this high, whatever room there is over it
FLIGHT_BEATS = 1.0  # they land on their lamps on the next beat
REST_BEATS = 0.5  # and fade there over this
BEAT_KEYS = 256  # drop k of beat j's burst draws from key j * BEAT_KEYS + k
BURSTS_ALIVE = math.ceil(FLIGHT_BEATS + REST_BEATS)  # bursts in the air at once, at the most


class Fountain(ParamParticles):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "anchor": anchor_param("Sprays from"),
            "palette": EffectParam(
                type="color_list", default=list(FOUNTAIN_PALETTE), label="Palette"
            ),
            "rate": EffectParam(
                type="float",
                default=30.0,
                min=5.0,
                max=120.0,
                step=5.0,
                label="Spray",
                description="Drops a second",
                bindable=True,
            ),
            "height_m": EffectParam(
                type="float",
                default=1.2,
                min=0.3,
                max=3.0,
                step=0.1,
                label="Height",
                description="Metres the spray goes up",
                bindable=True,
            ),
            "spread_m": EffectParam(
                type="float",
                default=2.0,
                min=0.2,
                max=5.0,
                step=0.1,
                label="Spread",
                description="Metres from the fountain the spray lands, at most",
            ),
            "burst": EffectParam(
                type="int",
                default=16,
                min=0,
                max=60,
                step=1,
                label="Burst",
                description="Drops in each beat's burst",
            ),
            "size": EffectParam(
                type="float",
                default=0.2,
                min=0.05,
                max=0.5,
                step=0.05,
                label="Drop size",
                description="Metres",
            ),
        }

    def positions(self, ctx: RenderContext, ground: Ground) -> Particles:
        origin = anchor_or_centre(ground.leds, str(self._values["anchor"])).astype(np.float64)
        return in_birth_order(self._spray(ctx, ground, origin), self._bursts(ctx, ground, origin))

    def _spray(
        self, ctx: RenderContext, ground: Ground, origin: NDArray[np.float64]
    ) -> tuple[Particles, F64]:
        """The steady spray: drops thrown up and out under gravity, until the floor; and when
        each was thrown."""
        values = self._values
        # No higher than the room over the anchor: past the ceiling a drop would flatten on it.
        height = float(values["height_m"])
        height = max(min(height, ground.ceiling - float(origin[2])), LEAST_RISE_M)
        up = math.sqrt(2.0 * GRAVITY * height)  # m/s to the height
        fall = max(float(origin[2]) - ground.floor, 0.0)
        longest = (up + math.sqrt(up * up + 2.0 * GRAVITY * fall)) / GRAVITY  # to the floor
        # The bursts' room is kept; ceil(rate * longest) + 1 drops are in the air at the most,
        # and 2 spare keep a rounding from tipping a count that comes out even.
        room = MAX_PARTICLES - BURSTS_ALIVE * int(values["burst"])
        every = 1.0 / min(float(values["rate"]), (room - 2) / longest)
        n = recent(ctx.t, every, longest)
        u = draws(self._seed, n, 4)
        born = (n + u[:, 0]) * every
        age = ctx.t - born
        speed = up * (0.85 + 0.15 * u[:, 1])  # up, m/s
        flight = 2.0 * speed / GRAVITY  # up and back down to the anchor's height
        out = float(values["spread_m"]) * np.sqrt(u[:, 3]) / flight  # m/s
        z = origin[2] + speed * age - 0.5 * GRAVITY * age * age
        kept = np.flatnonzero((age >= 0.0) & (z >= ground.floor))
        away, heading = out[kept] * age[kept], 2.0 * math.pi * u[kept, 2]
        pos = np.stack(
            [
                origin[0] + away * np.cos(heading),
                origin[1] + away * np.sin(heading),
                np.minimum(z[kept], ground.ceiling),
            ],
            axis=1,
        )
        glow = np.clip(1.5 - age[kept] / flight[kept], 0.0, 1.0)  # fades as it falls past
        colour = palette_at(self._palette, u[kept, 1]) * glow[:, None].astype(np.float32)
        return swarm(pos, colour, float(values["size"])), born[kept]

    def _bursts(
        self, ctx: RenderContext, ground: Ground, origin: NDArray[np.float64]
    ) -> tuple[Particles, F64]:
        """Each beat's burst: drops thrown from the anchor to the lamps; and when each was
        thrown, in seconds at the tempo of the moment."""
        values = self._values
        size, beats = int(values["burst"]), ctx.beats
        alive = fired(beats, FLIGHT_BEATS + REST_BEATS)
        beat = np.repeat(alive, size)
        u = draws(self._seed, beat * BEAT_KEYS + np.tile(np.arange(size), len(alive)), 3, stream=1)
        lamp = ground.lamps.pick(u[:, 0])
        landing = ground.on(lamp, u[:, 2])
        since = beats - beat.astype(np.float64)  # beats since the burst was thrown
        share = since / FLIGHT_BEATS  # 1: landed
        rise = float(values["height_m"]) * BURST_UP * (0.8 + 0.4 * u[:, 1])
        # An arc rises no more than fits under the lamp's ceiling: its top is at most there.
        fitted = rise_under(ground.ceiling_for(lamp), origin[2], landing[:, 2], rise)
        pos = arc(origin, landing, np.minimum(share, 1.0), fitted)
        # Only the backstop, for an anchor outside the lamp's band: the throw stops at the
        # ceiling and the floor, but never short of the lamp's own LEDs.
        pos[:, 2] = ground.within(lamp, pos[:, 2])
        glow = np.clip(1.0 - (share - 1.0) * FLIGHT_BEATS / REST_BEATS, 0.0, 1.0)
        colour = palette_at(self._palette, u[:, 1]) * glow[:, None].astype(np.float32)
        thrown = ctx.t - since * 60.0 / ctx.bpm
        return swarm(pos, colour, float(values["size"])), thrown
