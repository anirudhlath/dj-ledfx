"""Speaker waves' field (looks.json "speakers"): kicks send wavefronts out from each of the
anchor's points, snares bloom between them and hi-hats sparkle up high.

Until M7 brings the music's own kicks, snares and hats, the beat stands in for them
(M3 ruling 16): a kick on every beat, a snare on the second and fourth, hats on the
off-beat. Which high LEDs sparkle comes from the seed and the beat alone.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.color import palette_float
from dj_ledfx.effects.field import ParamField
from dj_ledfx.effects.field_tools import anchor_or_centre, distances, height01, smoothstep
from dj_ledfx.effects.params import EffectParam, level_param

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

# M3 ruling 17
KICK_COLOUR, SNARE_COLOUR, HAT_COLOUR, REST_COLOUR = "#ff5a1f", "#ffd23f", "#e8f4ff", "#05030a"
WAVE_M = 0.4  # a wavefront's thickness
BLOOM_M = 1.5  # a snare's reach from the middle of the speakers
HIGH_FROM, HIGH_TO = 0.55, 0.85  # where "up high" starts and is full, floor 0 to ceiling 1

F32 = NDArray[np.float32]


class SpeakerWaves(ParamField):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "anchor": EffectParam(
                type="anchor",
                default="",
                label="Speakers",
                description="Waves start at each of its points; none: the middle of the zone",
            ),
            "kick": EffectParam(type="color", default=KICK_COLOUR, label="Kick"),
            "snare": EffectParam(type="color", default=SNARE_COLOUR, label="Snare"),
            "hat": EffectParam(type="color", default=HAT_COLOUR, label="Hi-hat"),
            "rest": EffectParam(type="color", default=REST_COLOUR, label="Between"),
            "speed_m": EffectParam(
                type="float",
                default=6.0,
                min=1.0,
                max=30.0,
                step=0.5,
                label="Wave speed",
                description="Metres a second",
            ),
            "sparkle": EffectParam(
                type="float",
                default=0.15,
                min=0.0,
                max=1.0,
                step=0.01,
                label="Sparkle",
                description="The share of the high LEDs each hi-hat lights",
                bindable=True,
            ),
            "level": level_param(0.9),
        }

    def _prepare(self) -> None:
        super()._prepare()
        values = self._values
        colours = palette_float([values["kick"], values["snare"], values["hat"], values["rest"]])
        self._kick, self._snare, self._hat, self._rest = colours

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        values = self._values
        each, middle, high = self._per_leds(leds, self._sources)
        fade = np.float32(1.0 - ctx.beat_phase)
        since = ctx.beat_phase * 60.0 / max(ctx.bpm, 1.0)  # seconds since the beat
        gap = (each - np.float32(float(values["speed_m"]) * since)) / np.float32(WAVE_M)
        kick = np.exp(-(gap * gap)).max(axis=0) * fade
        snare = np.zeros_like(middle)
        if ctx.beat_index % 2 == 1:  # the second and fourth beats
            snare = np.exp(-np.square(middle / np.float32(BLOOM_M))) * fade * fade
        hat = np.zeros_like(high)
        if ctx.beat_phase >= 0.5:  # the off-beat, fading by the next beat
            lit = self._sparkles(ctx.beat_index, leds.count, float(values["sparkle"]))
            hat = high * lit * np.float32(2.0 * (1.0 - ctx.beat_phase))
        out = np.repeat(self._rest[None, :], leds.count, axis=0)
        for amount, colour in ((kick, self._kick), (snare, self._snare), (hat, self._hat)):
            out += (colour - out) * amount[:, None]
        frame: FloatRGB = (out * np.float32(values["level"])).astype(np.float32)
        return frame

    def _sparkles(self, beat_index: int, count: int, share: float) -> F32:
        draws = np.random.default_rng([self._seed % 2**32, beat_index % 2**63]).random(count)
        return (draws < share).astype(np.float32)

    def _sources(self, leds: LedSet) -> tuple[F32, F32, F32]:
        """Each LED's distance from each of the anchor's points (k, n), from their middle,
        and how high up it is (0 low, 1 high)."""
        anchor = self._values["anchor"]
        points = leds.space.anchor_points.get(anchor) if anchor else None
        if points is None or len(points) == 0:
            points = anchor_or_centre(leds, anchor)[None, :]
        each = np.stack([distances(leds, point) for point in points])
        middle = distances(leds, points.mean(axis=0).astype(np.float32))
        return each, middle, smoothstep(HIGH_FROM, HIGH_TO, height01(leds))
