"""Home sunset's field (looks.json "homesunset"): Sunset with the real sun for its sun.

The gradient is Sunset's, warm at the floor to deep blue at the ceiling; its warmth stands
where the sun stands on the home's plan, so at sunset the west side of the home is the
warmest (engine spec §7.3, plan ruling 6). With no sun (no location) it plays as Sunset
with no anchor.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from dj_ledfx.effects.context import SUN_AZIMUTH, SUN_ELEVATION
from dj_ledfx.effects.field_tools import reach, sun_point
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.effects.sunset_gradient import SunsetGradient, warmest_at

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB


class HomeSunset(SunsetGradient):
    """Sunset's settings but its anchor: the sun is the real one, at the frame's edge on
    its bearing and raised by its height (`sun_point()`), below the horizon as well."""

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {name: p for name, p in super().parameters().items() if name != "anchor"}

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        along = self._per_leds(leds, self._height)  # kept for these LEDs: the sun moves
        elevation = ctx.signals.get(SUN_ELEVATION, math.nan)
        azimuth = ctx.signals.get(SUN_AZIMUTH, math.nan)
        if math.isfinite(elevation) and math.isfinite(azimuth):
            sun = sun_point(leds, elevation, azimuth)
            along = warmest_at(along, reach(leds, sun))
        return self._painted(ctx, along)
