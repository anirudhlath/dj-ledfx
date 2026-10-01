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
