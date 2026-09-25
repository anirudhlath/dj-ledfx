"""Aurora's field (looks.json "aurora"): curtains that drift near the ceiling.

Folds run across the room and wander with seeded 3D noise; the colour climbs the palette
with height, green low in the curtain to violet at its top.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.field import ParamField
from dj_ledfx.effects.field_tools import height01, palette_at, palette_float, smoothstep
from dj_ledfx.effects.noise import fbm3
from dj_ledfx.effects.params import EffectParam

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

# Low in the curtain to high (ruling 17). Task 20's Morph layer shares it.
AURORA_PALETTE = ("#1cff8e", "#00c9a7", "#2a7fff", "#8b3dff")
DEFAULT_BAND = (0.55, 1.0)


class AuroraCurtains(ParamField):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(
                type="color_list", default=list(AURORA_PALETTE), label="Palette"
            ),
            "speed": EffectParam(
                type="float",
                default=1.0,
                min=0.1,
                max=3.0,
                step=0.05,
                label="Speed",
                bindable=True,
            ),
            "band": EffectParam(
                type="range",
                default=list(DEFAULT_BAND),
                min=0.0,
                max=1.0,
                label="Height band",
                description="Where the curtains hang, as a share of the ceiling height",
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
        speed: float = 1.0,
        band: Sequence[float] | None = None,
        level: float = 0.9,
    ) -> None:
        self._seed = 0
        self._apply_params(
            palette=list(palette or AURORA_PALETTE),
            speed=speed,
            band=list(band or DEFAULT_BAND),
            level=level,
        )

    def reseed(self, seed: int) -> None:
        self._seed = seed

    def _prepare(self) -> None:
        self._palette = palette_float(self._values["palette"])

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        values = self._values
        low, high = (float(edge) for edge in values["band"])
        speed = float(values["speed"])
        h = height01(leds)
        hang = smoothstep(low, (low + high) / 2.0, h) * (1.0 - smoothstep(high, high + 0.1, h))
        x = leds.pos[:, 0].astype(np.float64)
        y = leds.pos[:, 1].astype(np.float64)
        drift = ctx.t * 0.05 * speed
        noise = fbm3(
            np.column_stack([x * 0.4 + drift, y * 0.4, np.full(leds.count, drift * 0.5)]),
            self._seed,
            octaves=3,
        )
        folds = 0.5 + 0.5 * np.sin(
            2.0 * math.pi * (x * 0.3 + y * 0.15) + 6.0 * noise + ctx.t * 0.4 * speed
        )
        glow = hang * (0.2 + 0.8 * folds * folds) * float(values["level"])
        shade = 0.6 * np.clip((noise - 0.3) / 0.4, 0.0, 1.0) + 0.4 * h
        return (palette_at(self._palette, shade) * glow[:, None]).astype(np.float32)
