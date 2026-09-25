from __future__ import annotations

import numpy as np
from conftest import render_ctx
from map_home import leds_at

from dj_ledfx.effects.field_tools import palette_float
from dj_ledfx.effects.sunset_gradient import SUNSET_PALETTE, SunsetGradient

FLOOR_TO_CEILING = [(1.0, 1.0, 0.0), (1.0, 1.0, 1.5), (1.0, 1.0, 3.0)]


def _warmth(frame: np.ndarray) -> np.ndarray:
    """Red less blue: the palette's stops fall from floor to ceiling."""
    return frame[:, 0] - frame[:, 2]


def test_sunset_is_warm_at_the_floor_and_deep_blue_at_the_ceiling() -> None:
    frame = SunsetGradient().render(render_ctx(t=0.0), leds_at(FLOOR_TO_CEILING))

    palette = palette_float(SUNSET_PALETTE)
    assert np.allclose(frame[0], palette[0] * 0.85)  # the horizon is level at t=0
    assert np.allclose(frame[2], palette[-1] * 0.85)
    assert frame[0, 0] > frame[0, 2] and frame[2, 2] > frame[2, 0]
    assert np.all(np.diff(_warmth(frame)) < 0)


# Engine spec §9: "Sunset is warmest at its anchor".
def test_sunset_is_warmest_at_its_anchor() -> None:
    row = [(x, 0.0, 0.5) for x in (0.0, 1.0, 2.0, 3.0, 4.0)]
    leds = leds_at(row, anchors={"window": (0.0, 0.0, 0.5)})

    toward = SunsetGradient(anchor="window").render(render_ctx(t=0.0), leds)
    without = SunsetGradient().render(render_ctx(t=0.0), leds)
    gone = SunsetGradient(anchor="deleted").render(render_ctx(t=0.0), leds)

    assert np.all(np.diff(_warmth(toward)) < 0)
    assert np.allclose(without, without[0]) and np.array_equal(gone, without)


def test_warmth_lifts_the_warm_colours_and_level_dims_them() -> None:
    leds = leds_at(FLOOR_TO_CEILING)
    ctx = render_ctx(t=0.0)

    warm = SunsetGradient(warmth=1.0).render(ctx, leds)
    cool = SunsetGradient(warmth=0.0).render(ctx, leds)
    dim = SunsetGradient(level=0.4).render(ctx, leds)

    assert _warmth(warm)[1] > _warmth(cool)[1]  # the middle LED
    assert np.allclose(dim, SunsetGradient(level=0.8).render(ctx, leds) / 2)


def test_the_horizon_drifts_slowly() -> None:
    leds = leds_at(FLOOR_TO_CEILING)
    effect = SunsetGradient(drift_s=60.0)

    now = effect.render(render_ctx(t=0.0), leds)
    next_frame = effect.render(render_ctx(t=1 / 60), leds)
    later = effect.render(render_ctx(t=15.0), leds)

    assert np.abs(next_frame - now).max() < 0.01
    assert np.abs(later - now).max() > 0.02
    assert effect.render(render_ctx(t=0.0), leds_at([])).shape == (0, 3)
