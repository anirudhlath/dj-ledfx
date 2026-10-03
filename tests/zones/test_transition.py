"""Spec §5.3's transitions: which LEDs switch when, and how much of the new look each
shows part-way."""

from __future__ import annotations

import numpy as np
import pytest
from map_home import leds_at

from dj_ledfx.looks.model import TransitionKind
from dj_ledfx.zones.transition import new_share, switch_order

Point = tuple[float, float, float]
ROW: list[Point] = [(x, 1.0, 1.0) for x in (0.0, 1.0, 2.0, 3.0, 4.0)]  # west to east
COLUMN: list[Point] = [(1.0, y, 1.0) for y in (0.0, 1.0, 2.0, 3.0, 4.0)]  # north to south


def _share(kind: TransitionKind, points: list[Point], p: float) -> list[float]:
    leds = leds_at(points)
    return [round(float(x), 3) for x in new_share(kind, switch_order(kind, leds, 7), p, 5)[:, 0]]


@pytest.mark.parametrize("kind", ["fade", "cut"])
def test_a_fade_moves_every_led_together(kind: TransitionKind) -> None:
    assert switch_order(kind, leds_at(ROW), 7) is None
    assert _share(kind, ROW, 0.0) == [0.0] * 5
    assert _share(kind, ROW, 0.5) == [0.5] * 5
    assert _share(kind, ROW, 1.0) == [1.0] * 5


def test_a_wipe_sweeps_along_the_zones_longer_side() -> None:
    assert _share("wipe", ROW, 0.5) == [1.0, 1.0, 0.5, 0.0, 0.0]  # west first
    assert _share("wipe", COLUMN, 0.5) == [1.0, 1.0, 0.5, 0.0, 0.0]  # north first


def test_a_spread_grows_from_the_anchor_nearest_the_middle() -> None:
    leds = leds_at(ROW, anchors={"lamp": (2.2, 1.0, 1.0), "door": (9.0, 1.0, 1.0)})

    order = switch_order("spread", leds, 7)

    assert order is not None
    assert np.argsort(order).tolist()[:3] == [2, 3, 1]  # nearest the lamp first
    assert float(order.max()) == pytest.approx(1.0)


def test_a_spread_on_a_map_without_anchors_grows_from_the_middle() -> None:
    order = switch_order("spread", leds_at(ROW), 7)

    assert order is not None
    assert order.round(3).tolist() == [1.0, 0.5, 0.0, 0.5, 1.0]


def test_a_dissolve_is_random_but_the_same_for_the_same_seed() -> None:
    leds = leds_at(ROW)
    first, again, other = (switch_order("dissolve", leds, seed) for seed in (7, 7, 8))

    assert first is not None and again is not None and other is not None
    assert first.tolist() == again.tolist() and first.tolist() != other.tolist()
    assert ((0.0 <= first) & (first < 1.0)).all()


@pytest.mark.parametrize("kind", ["wipe", "spread", "dissolve"])
def test_every_led_starts_old_and_ends_new(kind: TransitionKind) -> None:
    assert _share(kind, ROW, 0.0) == [0.0] * 5
    assert _share(kind, ROW, 1.0) == [1.0] * 5
    assert _share(kind, ROW, 1.5) == [1.0] * 5  # past the end: still new


def test_a_zone_with_no_leds_has_no_order() -> None:
    assert switch_order("wipe", leds_at([]), 7) is None
