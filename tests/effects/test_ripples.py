from __future__ import annotations

import statistics
import time

import numpy as np
import pytest
from conftest import CallCounts, render_ctx
from map_home import leds_at, seeded_ledset

from dj_ledfx.effects.color import palette_at, palette_float
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


# M8: each drop still alive is drawn as a level ring where it landed, as far out as it has
# travelled, in its crest's colour; gone drops aren't.
def test_each_live_drop_is_drawn_as_a_level_ring_where_it_landed() -> None:
    effect, leds = _ripples(), leds_at(ACROSS_THE_ROOM)
    when, where = effect.drop(0, leds)
    palette = palette_float(list(RIPPLE_PALETTE))

    for age in (0.5, 2.0):
        ctx = render_ctx(when + age)
        effect.render(ctx, leds)
        fx = effect.in_space(ctx, leds)
        assert fx is not None and fx.rings.count == 1 and fx.rings.circle.all()
        assert np.allclose(fx.rings.centre[0], where) and np.isclose(fx.rings.radius[0], age)
        crest = palette_at(palette, np.array([np.exp(-age / 3.0)], dtype=np.float32)) * 0.9
        assert np.allclose(fx.rings.colour, crest) and np.isclose(fx.rings.width[0], 0.7)

    gone = render_ctx(when + LIFE_FADES * 3.0 + 0.1)  # past its life, before the next drop
    assert effect.drop(1, leds)[0] > gone.t
    assert effect.in_space(gone, leds) is None


def test_several_live_drops_are_drawn_oldest_first_each_with_its_own_ring() -> None:
    effect = Ripples(drops_per_min=20.0, speed=1.0, fade_s=3.0)  # a drop every 3 s, 9 s alive
    effect.reseed(3)
    leds, palette = leds_at(ACROSS_THE_ROOM), palette_float(list(RIPPLE_PALETTE))
    t = effect.drop(12, leds)[0] + 0.25  # drop 12 has just landed
    drops = [effect.drop(k, leds) for k in range(5, 13)]
    alive = [(when, where) for when, where in drops if 0.0 <= t - when <= LIFE_FADES * 3.0]
    assert len(alive) >= 3

    fx = effect.in_space(render_ctx(t), leds)

    assert fx is not None and fx.rings.count == len(alive)
    assert np.allclose(fx.rings.centre, [where for _, where in alive])
    assert np.allclose(fx.rings.radius, [t - when for when, _ in alive])
    strength = np.array([np.exp(-(t - when) / 3.0) for when, _ in alive], dtype=np.float32)
    assert np.allclose(fx.rings.colour, palette_at(palette, strength) * 0.9)
    assert np.all(np.diff(fx.rings.radius) < 0.0)  # the oldest, the farthest out, first


def test_a_frame_works_out_its_live_drops_once_for_its_colours_and_its_rings(
    call_counts: CallCounts,
) -> None:
    effect, leds = _ripples(), leds_at(ACROSS_THE_ROOM)
    ctx = render_ctx(effect.drop(10, leds)[0] + 1.0)
    call_counts.spy(Ripples, "drop")

    effect.render(ctx, leds)
    once = call_counts.calls["drop"]
    fx = effect.in_space(ctx, leds)

    assert fx is not None and fx.rings.count == 1
    assert call_counts.calls["drop"] == once  # in_space took render's drops
    effect.render(render_ctx(ctx.t + 1 / 60), leds)  # the next frame works them out again
    assert call_counts.calls["drop"] == 2 * once
