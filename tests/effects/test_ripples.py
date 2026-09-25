from __future__ import annotations

import statistics
import time

import numpy as np
import pytest
from conftest import render_ctx
from map_home import leds_at, seeded_ledset

from dj_ledfx.effects.field_tools import palette_float
from dj_ledfx.effects.ripples import LIFE_FADES, RIPPLE_PALETTE, Ripples

ACROSS_THE_ROOM = [(x, 2.0, 0.5) for x in np.linspace(0.0, 6.0, 13)]
ONE_A_MINUTE = 60.0  # drops_per_min=1: drop k lands within [60 k, 60 k + 48) s


def _ripples() -> Ripples:
    effect = Ripples(drops_per_min=1.0, speed=1.0, fade_s=3.0)
    effect.reseed(3)
    return effect


# Engine spec §9: "a ripple reaches LEDs in order of distance".
def test_a_ripple_reaches_leds_in_order_of_distance() -> None:
    leds = leds_at(ACROSS_THE_ROOM)
    effect = _ripples()
    when, where = effect.drop(10, leds)
    assert 10 * ONE_A_MINUTE <= when < 11 * ONE_A_MINUTE and where[2] == 0.0  # on the floor

    times = when + np.arange(0.0, 8.0, 0.02)
    brightness = np.array([effect.render(render_ctx(t=float(t)), leds).sum(axis=1) for t in times])
    peaks = times[brightness.argmax(axis=0)]

    order = np.argsort(np.linalg.norm(leds.pos - where, axis=1))
    assert np.all(np.diff(peaks[order]) >= 0.0)
    assert peaks[order[-1]] - peaks[order[0]] > 1.0  # it takes time to cross the room


def test_between_drops_the_floor_rests_on_the_first_colour() -> None:
    leds = leds_at(ACROSS_THE_ROOM)
    effect = _ripples()
    # Drop 10 lands by 648 s and fades out within LIFE_FADES * 3 s; drop 11 lands from 660 s.
    assert 648.0 + LIFE_FADES * 3.0 < 658.0

    rest = effect.render(render_ctx(t=658.0), leds)

    assert np.allclose(rest, palette_float(RIPPLE_PALETTE)[0] * 0.9)


def test_ripples_repeat_with_their_seed() -> None:
    leds = leds_at(ACROSS_THE_ROOM)
    first, again, other = _ripples(), _ripples(), Ripples(drops_per_min=1.0)
    other.reseed(4)

    assert first.drop(7, leds)[0] == again.drop(7, leds)[0]
    assert first.drop(7, leds)[0] != other.drop(7, leds)[0]
    t = first.drop(7, leds)[0] + 2.0
    assert np.array_equal(first.render(render_ctx(t=t), leds), again.render(render_ctx(t=t), leds))


# M2 review M12: the most drops alive at once (60 a minute, each fading over 30 s), on this
# home's LEDs, within the frame budget (engine spec §9).
@pytest.mark.perf
def test_ripples_at_their_densest_render_in_under_5_ms() -> None:
    leds = seeded_ledset()
    effect = Ripples(drops_per_min=60.0, speed=0.2, fade_s=10.0)
    effect.reseed(3)
    durations = []
    for step in range(240):
        started = time.perf_counter()
        effect.render(render_ctx(t=1000.0 + step / 60), leds)
        durations.append(time.perf_counter() - started)
    assert statistics.median(durations) < 0.005
