from __future__ import annotations

import math

import numpy as np
from conftest import tempo_ctx
from map_home import leds_at

from dj_ledfx.effects.lighthouse_beam import LighthouseBeam

# East, north, west and south of the TV, a metre away.
AROUND = [(math.cos(k * math.pi / 2), math.sin(k * math.pi / 2), 1.0) for k in range(4)]
TV = {"tv": (0.0, 0.0, 1.0)}


def test_the_beam_turns_once_a_bar() -> None:
    effect = LighthouseBeam(anchor="tv", width_deg=20.0)
    leds = leds_at(AROUND, anchors=TV)

    for beat in range(4):  # a quarter turn a beat
        frame = effect.render(tempo_ctx(4.0 + beat), leds)

        assert frame.sum(axis=1).argmax() == beat
        assert np.allclose(frame[(beat + 2) % 4], 0.0)  # dark behind it


# M8: the beam in space is the upright half-plane from the anchor towards the LED it lights.
def test_the_beam_is_drawn_as_a_half_plane_from_the_anchor_towards_its_bearing() -> None:
    effect = LighthouseBeam(anchor="tv", width_deg=20.0)
    leds = leds_at(AROUND, anchors=TV)

    for beat in range(4):
        ctx = tempo_ctx(4.0 + beat)
        frame = effect.render(ctx, leds)
        fx = effect.in_space(ctx, leds)

        [point], [ray], [normal] = fx.planes.point, fx.planes.ray, fx.planes.normal
        assert np.allclose(point, TV["tv"])
        assert np.allclose(ray, AROUND[beat] - np.array(TV["tv"]), atol=1e-6)  # towards it
        assert np.isclose(np.dot(ray, normal), 0.0) and normal[2] == 0.0  # upright
        assert np.isclose(fx.planes.width[0], math.radians(20.0))
        assert np.allclose(fx.planes.colour[0], frame[beat])
