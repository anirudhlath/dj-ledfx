"""Plays a 1D strip effect along a zone's LEDs (spec §5.1).

M1 uses the LED order along the zone's devices; M2 adds projecting each LED's
position onto an axis, linear or radial like today's mappings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dj_ledfx.effects.color import to_float_rgb
from dj_ledfx.effects.context import to_beat_context
from dj_ledfx.effects.field import FieldEffect

if TYPE_CHECKING:
    from dj_ledfx.effects.base import StripEffect
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB


class StripAdapter(FieldEffect, register=False):
    def __init__(self, inner: StripEffect) -> None:
        self.inner = inner

    def get_params(self) -> dict[str, Any]:
        return self.inner.get_params()

    def set_params(self, **kwargs: Any) -> None:
        self.inner.set_params(**kwargs)

    def reseed(self, seed: int) -> None:
        self.inner.reseed(seed)

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        return to_float_rgb(self.inner.render(to_beat_context(ctx), leds.count))
