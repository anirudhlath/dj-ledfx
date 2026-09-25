from __future__ import annotations

import numpy as np
from conftest import render_ctx
from map_home import leds_at

from dj_ledfx.effects.color_carousel import ColorCarousel

# East, south, west and north of (2, 2) (y runs south on the map).
AROUND = [(3.0, 2.0, 1.0), (2.0, 3.0, 1.0), (1.0, 2.0, 1.0), (2.0, 1.0, 1.0)]
EAST, SOUTH, WEST, NORTH = range(4)


def test_each_lamp_takes_its_hue_from_its_angle_around_the_middle() -> None:
    leds = leds_at(AROUND, anchors={"middle": (2.0, 2.0, 0.0)})

    frame = ColorCarousel(anchor="middle", level=1.0).render(render_ctx(t=0.0), leds)

    assert np.allclose(frame[EAST], [1.0, 0.0, 0.0])  # hue 0
    assert np.allclose(frame[SOUTH], [0.5, 1.0, 0.0])  # a quarter turn on
    assert np.allclose(frame[WEST], [0.0, 1.0, 1.0])  # opposite: half a turn
    assert np.allclose(frame[NORTH], [0.5, 0.0, 1.0])


def test_the_rainbow_circles_once_per_turn() -> None:
    leds = leds_at(AROUND)  # no anchor: the middle of the zone, (2, 2)
    effect = ColorCarousel(turn_s=60.0)

    start = effect.render(render_ctx(t=0.0), leds)

    assert np.allclose(effect.render(render_ctx(t=15.0), leds)[EAST], start[SOUTH])
    assert np.allclose(effect.render(render_ctx(t=60.0), leds), start, atol=1e-5)
    assert np.allclose(start.max(axis=1), 0.9)  # full saturation at the level


def test_saturation_washes_the_colours_out() -> None:
    frame = ColorCarousel(saturation=0.0, level=0.5).render(render_ctx(t=3.0), leds_at(AROUND))

    assert np.allclose(frame, 0.5)
