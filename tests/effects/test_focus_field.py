from __future__ import annotations

import numpy as np
from conftest import render_ctx
from map_home import leds_at

from dj_ledfx.effects.field_tools import palette_float
from dj_ledfx.effects.focus_field import FocusField

NEAR, MIDDLE, FAR = 0, 1, 2
FROM_THE_SEAT = [(2.5, 2.0, 0.5), (5.0, 2.0, 0.5), (8.0, 2.0, 0.5)]
SEAT = {"seat": (2.0, 2.0, 0.5)}


def test_calm_and_warm_near_the_anchor_busy_and_colourful_far_from_it() -> None:
    effect = FocusField(anchor="seat", calm_m=2.0)
    effect.reseed(5)
    leds = leds_at(FROM_THE_SEAT, anchors=SEAT)

    # 30 s, twice a second
    frames = np.array([effect.render(render_ctx(t=100.0 + step / 2), leds) for step in range(60)])

    calm = palette_float(["#ffb070"])[0] * 0.9
    assert np.allclose(frames[:, NEAR], calm)  # steady, and warm: red over blue
    assert calm[0] > calm[2]
    assert frames[:, FAR].std(axis=0).max() > 0.05  # it keeps changing
    assert set(frames[:, FAR].argmax(axis=1)) == {0, 1, 2}  # red, green and blue in turn
    assert not np.allclose(frames[:, MIDDLE], calm)  # on the way between the two


def test_without_its_anchor_the_middle_of_the_zone_is_calm() -> None:
    effect = FocusField(anchor="gone", calm_m=1.0)
    leds = leds_at([(0.0, 0.0, 0.5), (3.0, 0.0, 0.5), (6.0, 0.0, 0.5)])

    frame = effect.render(render_ctx(t=4.0), leds)

    assert np.allclose(frame[1], palette_float(["#ffb070"])[0] * 0.9)
