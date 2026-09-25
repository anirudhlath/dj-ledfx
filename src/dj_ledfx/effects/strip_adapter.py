"""Plays a 1D strip effect across a zone's LEDs (spec §5.1).

Each LED's position is projected onto the strip: linearly along an axis of the home, or
radially out from a centre, like the old scene mappings. The strip is rendered with one
sample per LED and each LED takes the sample nearest its place. With `order`, the strip
runs along the LEDs in zone order, as in M1, and so it does when the LEDs span less than
MIN_SPAN_M along the axis (or out from the centre): a strip running north-south would
otherwise show one colour on the classics' east default.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from dj_ledfx.effects.color import to_float_rgb
from dj_ledfx.effects.context import to_beat_context
from dj_ledfx.effects.field import FieldEffect
from dj_ledfx.effects.field_tools import anchor_or_centre
from dj_ledfx.effects.params import EffectParam, check_setting

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from dj_ledfx.effects.base import StripEffect
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

MIN_SPAN_M = 0.05
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
        self._projection = {key: str(param.default) for key, param in PROJECTION_PARAMS.items()}
        # Which strip sample each LED takes (None: LED order), for the last LED set seen.
        # It depends only on the LEDs and the projection settings.
        self._index: tuple[LedSet, NDArray[np.intp] | None] | None = None

    def get_params(self) -> dict[str, Any]:
        return self.inner.get_params()

    def set_params(self, **kwargs: Any) -> None:
        """Take the projection settings and hand the rest to the strip effect. Everything
        is checked before anything changes."""
        own = {key: kwargs.pop(key) for key in list(kwargs) if key in PROJECTION_PARAMS}
        for key, value in own.items():
            check_setting(key, PROJECTION_PARAMS[key], value)
        self.inner.set_params(**kwargs)
        self._projection.update({key: str(value) for key, value in own.items()})
        self._index = None

    def reseed(self, seed: int) -> None:
        self.inner.reseed(seed)

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        strip = to_float_rgb(self.inner.render(to_beat_context(ctx), leds.count))
        if self._index is None or self._index[0] is not leds:
            place = self._place(leds) if leds.count > 1 else None
            index = None if place is None else np.rint(place * (leds.count - 1)).astype(np.intp)
            self._index = (leds, index)
        index = self._index[1]
        return strip if index is None else strip[index]

    def _place(self, leds: LedSet) -> NDArray[np.float64] | None:
        """Each LED's place along the strip, 0..1. None: the strip runs in LED order."""
        mapping = self._projection["mapping"]
        if mapping == "order":
            return None
        positions = leds.pos.astype(np.float64)
        if mapping == "radial":
            centre = anchor_or_centre(leds, self._projection["centre"]).astype(np.float64)
            along = np.linalg.norm(positions - centre, axis=1)
            low = 0.0
        else:
            along = positions @ np.asarray(AXES[self._projection["axis"]], dtype=np.float64)
            low = float(along.min())
        span = float(along.max()) - low
        if span < MIN_SPAN_M:
            return None
        place: NDArray[np.float64] = (along - low) / span
        return place
