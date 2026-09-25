"""Ripples' field (looks.json "ripples"): drops land on the floor and send rings outward.

Stateless: drop k's landing time and place come from the seed and k alone (drop()), and
a frame draws the rings of the drops still alive. A ring reaches each LED when it has
travelled the LED's 3D distance from the drop (engine spec §9: "a ripple reaches LEDs in
order of distance"). Each drop's random draws are kept while it may be alive, and the
zone's footprint while the LED set is the same.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.field import ParamField
from dj_ledfx.effects.field_tools import distances, palette_at, palette_float
from dj_ledfx.effects.params import EffectParam

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

# At rest to a ring's crest, each stop brighter than the last (ruling 17).
RIPPLE_PALETTE = ("#06163a", "#1450c8", "#46b4ff", "#e6f8ff")
RING_WIDTH_M = 0.35
LIFE_FADES = 3.0  # a ring is dropped after this many fade times (e^-3: 5% left)
LANDING_SPREAD = 0.8  # drop k lands in the first 80% of its interval


class Ripples(ParamField):
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
            "level": EffectParam(
                type="float",
                default=0.9,
                min=0.0,
                max=1.0,
                step=0.01,
                label="Level",
                bindable=True,
            ),
        }

    def __init__(
        self,
        palette: list[str] | None = None,
        drops_per_min: float = 10.0,
        speed: float = 0.9,
        fade_s: float = 3.0,
        level: float = 0.9,
    ) -> None:
        self._seed = 0
        self._apply_params(
            palette=list(palette or RIPPLE_PALETTE),
            drops_per_min=drops_per_min,
            speed=speed,
            fade_s=fade_s,
            level=level,
        )

    def reseed(self, seed: int) -> None:
        self._seed = seed
        self._draws.clear()

    def _prepare(self) -> None:
        self._palette = palette_float(self._values["palette"])
        self._draws: dict[int, NDArray[np.float64]] = getattr(self, "_draws", {})
        self._footprint: tuple[LedSet, NDArray[np.float32], NDArray[np.float32], float] | None
        self._footprint = getattr(self, "_footprint", None)

    def _draw(self, k: int) -> NDArray[np.float64]:
        """Drop k's three random numbers: when in its interval, and where."""
        u = self._draws.get(k)
        if u is None:
            u = self._draws[k] = np.random.default_rng([self._seed % 2**32, k % 2**63]).random(3)
        return u

    def _bounds(self, leds: LedSet) -> tuple[NDArray[np.float32], NDArray[np.float32], float]:
        """The zone's footprint, and its floor: the map's, or with no map the lowest LED."""
        if self._footprint is None or self._footprint[0] is not leds:
            low, high = leds.pos.min(axis=0), leds.pos.max(axis=0)
            self._footprint = (leds, low, high, 0.0 if leds.space.ceiling else float(low[2]))
        return self._footprint[1:]

    def _interval(self) -> float:
        return 60.0 / float(self._values["drops_per_min"])

    def drop(self, k: int, leds: LedSet) -> tuple[float, NDArray[np.float32]]:
        """Drop k: when it lands (s, on the render clock) and where, on the floor of the
        zone's footprint. leds must hold at least one LED."""
        u = self._draw(k)
        when = (k + LANDING_SPREAD * float(u[0])) * self._interval()
        low, high, floor = self._bounds(leds)
        where = np.array(
            [low[0] + u[1] * (high[0] - low[0]), low[1] + u[2] * (high[1] - low[1]), floor],
            dtype=np.float32,
        )
        return when, where

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        values = self._values
        interval, fade = self._interval(), float(values["fade_s"])
        speed, life = float(values["speed"]), LIFE_FADES * fade
        first = math.floor((ctx.t - life) / interval) - 1  # the oldest drop that may be alive
        last = math.floor(ctx.t / interval)  # no later drop has landed yet
        for gone in [k for k in self._draws if k < first]:
            del self._draws[gone]
        wave = np.zeros(leds.count, dtype=np.float32)
        for k in range(first, last + 1):
            when, where = self.drop(k, leds)
            age = ctx.t - when
            if not 0.0 <= age <= life:
                continue
            gap = (distances(leds, where) - np.float32(speed * age)) / np.float32(RING_WIDTH_M)
            ring = np.exp(-(gap * gap)) * np.float32(math.exp(-age / fade))
            np.maximum(wave, ring, out=wave)
        colours = palette_at(self._palette, wave)
        return (colours * np.float32(values["level"])).astype(np.float32)
