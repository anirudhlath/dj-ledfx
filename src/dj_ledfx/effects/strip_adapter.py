"""Plays a 1D strip effect across a zone's LEDs (spec §5.1).

Each LED's position is projected onto the strip: linearly along an axis of the home, or
radially out from a centre, like the old scene mappings. The strip is rendered with one
sample per LED and each LED takes the sample nearest its place. With `order`, the strip
runs along the LEDs in zone order, as in M1.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from dj_ledfx.effects.color import to_float_rgb
from dj_ledfx.effects.context import to_beat_context
from dj_ledfx.effects.field import FieldEffect
from dj_ledfx.effects.field_tools import anchor_or_centre
from dj_ledfx.effects.params import EffectParam, check_setting
from dj_ledfx.spatial.mapping import LinearMapping, RadialMapping

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from dj_ledfx.effects.base import StripEffect
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

AXES: dict[str, tuple[float, float, float]] = {
    "east": (1.0, 0.0, 0.0),
    "south": (0.0, 1.0, 0.0),
    "up": (0.0, 0.0, 1.0),
}
PROJECTION_PARAMS: dict[str, EffectParam] = {
    "mapping": EffectParam(
        type="choice",
        default="linear",
        choices=["linear", "radial", "order"],
        label="Mapping",
        description="Along an axis, out from a centre, or in LED order",
    ),
    "axis": EffectParam(type="choice", default="east", choices=list(AXES), label="Axis"),
    "centre": EffectParam(type="anchor", default="", label="Centre"),
}


class StripAdapter(FieldEffect, register=False):
    # parameters() stays empty: the settings below are the adapter's own, checked by
    # set_params, and the schema lists them for strip kinds (looks/model.py).
    def __init__(self, inner: StripEffect) -> None:
        self.inner = inner
        self._mapping = str(PROJECTION_PARAMS["mapping"].default)
        self._axis = str(PROJECTION_PARAMS["axis"].default)
        self._centre = str(PROJECTION_PARAMS["centre"].default)

    def get_params(self) -> dict[str, Any]:
        return self.inner.get_params()

    def set_params(self, **kwargs: Any) -> None:
        """Take the projection settings and hand the rest to the strip effect. Everything
        is checked before anything changes."""
        own = {key: kwargs.pop(key) for key in list(kwargs) if key in PROJECTION_PARAMS}
        for key, value in own.items():
            check_setting(key, PROJECTION_PARAMS[key], value)
        self.inner.set_params(**kwargs)
        self._mapping = str(own.get("mapping", self._mapping))
        self._axis = str(own.get("axis", self._axis))
        self._centre = str(own.get("centre", self._centre))

    def reseed(self, seed: int) -> None:
        self.inner.reseed(seed)

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        count = leds.count
        strip = to_float_rgb(self.inner.render(to_beat_context(ctx), count))
        if self._mapping == "order" or count < 2:
            return strip
        index = np.rint(self._place(leds) * (count - 1)).astype(np.intp)
        return strip[index]

    def _place(self, leds: LedSet) -> NDArray[np.float64]:
        """Each LED's place along the strip, 0..1."""
        positions = leds.pos.astype(np.float64)
        if self._mapping == "radial":
            x, y, z = (float(value) for value in anchor_or_centre(leds, self._centre))
            return RadialMapping(center=(x, y, z)).map_positions(positions)
        return LinearMapping(direction=AXES[self._axis]).map_positions(positions)
