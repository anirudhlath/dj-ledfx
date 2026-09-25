from __future__ import annotations

import numpy as np
from conftest import render_ctx
from map_home import leds_at

from dj_ledfx.effects.aurora_curtains import AuroraCurtains

LOW_AND_HIGH = [(1.0, 1.0, 0.3), (1.0, 1.0, 2.7)]
UNDER_THE_CEILING = [(x * 0.5, 1.0, 2.7) for x in range(10)]


def test_the_curtains_hang_near_the_ceiling() -> None:
    frame = AuroraCurtains().render(render_ctx(t=100.0), leds_at(LOW_AND_HIGH))

    assert np.all(frame[0] == 0.0)
    assert frame[1].max() > 0.1


def test_the_band_says_where_they_hang() -> None:
    frame = AuroraCurtains(band=[0.0, 0.3]).render(render_ctx(t=100.0), leds_at(LOW_AND_HIGH))

    assert frame[0].max() > 0.05
    assert np.all(frame[1] == 0.0)


def test_the_curtains_drift_and_repeat_with_their_seed() -> None:
    leds = leds_at(UNDER_THE_CEILING)
    first, again, other = AuroraCurtains(), AuroraCurtains(), AuroraCurtains()
    first.reseed(1)
    again.reseed(1)
    other.reseed(2)

    now = first.render(render_ctx(t=100.0), leds)

    assert np.array_equal(now, again.render(render_ctx(t=100.0), leds))
    assert not np.allclose(now, other.render(render_ctx(t=100.0), leds))
    assert np.abs(first.render(render_ctx(t=103.0), leds) - now).max() > 0.01
    faster = AuroraCurtains(speed=3.0)
    faster.reseed(1)
    assert not np.allclose(faster.render(render_ctx(t=103.0), leds), now)
