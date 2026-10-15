"""Ripples' field (looks.json "ripples"): drops land on the floor and send rings outward.

Stateless: drop k's landing time and place come from the seed and k alone (drop()), and
a frame draws the rings of the drops still alive. A ring reaches each LED when it has
travelled the LED's 3D distance from the drop (engine spec §9: "a ripple reaches LEDs in
order of distance"). Each drop's random draws are kept while it may be alive, and the
zone's footprint while the LED set is the same; the drops alive at a moment are worked out
once, for the frame's colours and its rings in space alike.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.color import palette_at
from dj_ledfx.effects.field import ParamField
from dj_ledfx.effects.field_tools import band, distances
from dj_ledfx.effects.fx import Fx, rings
from dj_ledfx.effects.params import EffectParam, level_param

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

# At rest to a ring's crest, each stop brighter than the last (ruling 17).
RIPPLE_PALETTE = ("#06163a", "#1450c8", "#46b4ff", "#e6f8ff")
RING_WIDTH_M = 0.35
LIFE_FADES = 3.0  # a ring is dropped after this many fade times (e^-3: 5% left)
LANDING_SPREAD = 0.8  # drop k lands in the first 80% of its interval

_Drop = tuple[NDArray[np.float32], float, float]  # where it landed, its ring's radius, strength


class Ripples(ParamField):
    # The drops alive at the last moment asked, on the LEDs asked: render() and in_space()
    # share them within a frame.
    _alive_at: tuple[float, LedSet, list[_Drop]] | None

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(
                type="color_list", default=list(RIPPLE_PALETTE), label="Palette"
            ),
            "drops_per_min": EffectParam(
                type="float",
                default=10.0,
                min=1.0,
                max=60.0,
                step=1.0,
                label="Drops per minute",
                bindable=True,
            ),
            "speed": EffectParam(
                type="float",
                default=0.9,
                min=0.2,
                max=3.0,
                step=0.1,
                label="Ring speed",
                description="Metres a second",
            ),
            "fade_s": EffectParam(
                type="float", default=3.0, min=1.0, max=10.0, step=0.5, label="Fade"
            ),
            "level": level_param(0.9),
        }

    def reseed(self, seed: int) -> None:
        super().reseed(seed)
        self._draws.clear()
        self._alive_at = None

    def _prepare(self) -> None:
        super()._prepare()
        self._draws: dict[int, NDArray[np.float64]] = getattr(self, "_draws", {})
        self._alive_at = None

    def _draw(self, k: int) -> NDArray[np.float64]:
        """Drop k's three random numbers: when in its interval, and where."""
        u = self._draws.get(k)
        if u is None:
            u = self._draws[k] = self._rng(k).random(3)
        return u

    def _interval(self) -> float:
        return 60.0 / float(self._values["drops_per_min"])

    def drop(self, k: int, leds: LedSet) -> tuple[float, NDArray[np.float32]]:
        """Drop k: when it lands (s, on the render clock) and where, on the floor of the
        zone's footprint. leds must hold at least one LED."""
        u = self._draw(k)
        when = (k + LANDING_SPREAD * float(u[0])) * self._interval()
        low, high = leds.bounds  # the zone's footprint
        floor = 0.0 if leds.space.ceiling else float(low[2])  # the map's, or the lowest LED
        where = np.array(
            [low[0] + u[1] * (high[0] - low[0]), low[1] + u[2] * (high[1] - low[1]), floor],
            dtype=np.float32,
        )
        return when, where

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        wave = np.zeros(leds.count, dtype=np.float32)
        for where, radius, strength in self._alive(ctx, leds):
            ring = band(distances(leds, where), radius, RING_WIDTH_M)
            ring *= np.float32(strength)
            np.maximum(wave, ring, out=wave)
        colours = palette_at(self._palette, wave)
        return (colours * np.float32(self._values["level"])).astype(np.float32)

    def in_space(self, ctx: RenderContext, leds: LedSet) -> Fx | None:
        """Each live drop's ring: a level circle on the floor where it landed, as far out as
        it has travelled, in the colour its crest lights an LED."""
        alive = self._alive(ctx, leds)
        if not alive:
            return None
        strength = np.array([each for _, _, each in alive], dtype=np.float32)
        crest = palette_at(self._palette, strength) * np.float32(self._values["level"])
        return Fx(
            rings=rings(
                [where for where, _, _ in alive],
                [radius for _, radius, _ in alive],
                2.0 * RING_WIDTH_M,
                crest,
                circle=True,
            )
        )

    def _alive(self, ctx: RenderContext, leds: LedSet) -> list[_Drop]:
        """Each drop still alive at ctx's moment, oldest first: where it landed, how far its
        ring has travelled, and how strong it still is (1 as it lands, fading). Worked out
        once for a moment and an LED set. Draws of drops gone are let go."""
        kept = self._alive_at
        if kept is not None and kept[0] == ctx.t and kept[1] is leds:
            return kept[2]
        interval, fade = self._interval(), float(self._values["fade_s"])
        speed, life = float(self._values["speed"]), LIFE_FADES * fade
        first = math.floor((ctx.t - life) / interval) - 1  # the oldest drop that may be alive
        last = math.floor(ctx.t / interval)  # no later drop has landed yet
        for gone in [k for k in self._draws if k < first]:
            del self._draws[gone]
        alive: list[_Drop] = []
        for k in range(first, last + 1):
            when, where = self.drop(k, leds)
            age = ctx.t - when
            if 0.0 <= age <= life:
                alive.append((where, speed * age, math.exp(-age / fade)))
        self._alive_at = (ctx.t, leds, alive)
        return alive
