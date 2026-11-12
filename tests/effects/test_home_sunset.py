from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import numpy as np
import pytest
from conftest import CallCounts, render_ctx
from map_home import leds_at, seeded_ledset

from dj_ledfx.effects import home_sunset
from dj_ledfx.effects.context import SUN_AZIMUTH, SUN_ELEVATION, RenderContext, SignalView
from dj_ledfx.effects.field import FieldEffect
from dj_ledfx.effects.field_tools import sun_point
from dj_ledfx.effects.home_sunset import HomeSunset
from dj_ledfx.effects.ledset import LedSet, Space
from dj_ledfx.effects.registry import get_effect_class
from dj_ledfx.effects.sunset_gradient import SunsetGradient

# A row of LEDs along the east-west line (x east, y south), one height up. They are the LEDs
# a test looks at; the two beyond them fix the frame at a box from (0, 0, 0) to (4, 2, 2),
# since a row at one height has no depth or height of its own.
ROW = [(float(x), 1.0, 1.0) for x in range(5)]
BOX = [(0.0, 0.0, 0.0), (4.0, 2.0, 2.0)]
WEST, EAST = 0, 4  # the row's ends


def _row(north_offset_deg: float = 0.0) -> LedSet:
    space = Space(ceiling=3.0, north_offset_deg=north_offset_deg)
    return leds_at([*ROW, *BOX], space=space)


def _sun(elevation: float, azimuth: float, t: float = 0.0) -> RenderContext:
    return replace(
        render_ctx(t=t), signals=SignalView({SUN_ELEVATION: elevation, SUN_AZIMUTH: azimuth})
    )


def _warm(frame: np.ndarray, led: int) -> tuple[float, float]:
    """An LED's red and its blue: the palette's stops lose red and gain blue going up."""
    return float(frame[led, 0]), float(frame[led, 2])


def test_the_sun_point_is_where_the_stage_draws_it_on_the_zones_frame() -> None:
    leds = _row()

    # The east edge's middle, at the frame's top; the south edge's middle.
    assert sun_point(leds, 0.0, 90.0) == pytest.approx((4.0, 1.0, 2.0))
    assert sun_point(leds, 0.0, 180.0) == pytest.approx((2.0, 2.0, 2.0))
    assert sun_point(leds, 0.0, 270.0) == pytest.approx((0.0, 1.0, 2.0))
    assert sun_point(leds, 0.0, 0.0) == pytest.approx((2.0, 0.0, 2.0))
    # Overhead it is over the frame's middle, `exit` above its top: 2 m through the east edge,
    # 1 m through the south edge.
    assert sun_point(leds, 90.0, 90.0) == pytest.approx((2.0, 1.0, 4.0))
    assert sun_point(leds, 90.0, 180.0) == pytest.approx((2.0, 1.0, 3.0))
    # Between, it is raised along the way: 60 degrees up is half way in, `exit` times sin 60 high.
    assert sun_point(leds, 60.0, 90.0) == pytest.approx((3.0, 1.0, 2.0 + 2.0 * 3**0.5 / 2.0))
    # Below the horizon it is below the frame's top.
    assert sun_point(leds, -30.0, 90.0) == pytest.approx((2.0 + 2.0 * 3**0.5 / 2.0, 1.0, 1.0))
    # North turned 90 degrees puts a sun due north of the home on the east edge.
    assert sun_point(_row(90.0), 0.0, 0.0) == pytest.approx((4.0, 1.0, 2.0))
    assert sun_point(leds, 0.0, 0.0).dtype == np.float32


def test_home_sunset_is_warmest_where_the_sun_stands() -> None:
    leds = _row()

    frame = HomeSunset().render(_sun(2.0, 270.0), leds)  # low in the west

    (west_red, west_blue), (east_red, east_blue) = _warm(frame, WEST), _warm(frame, EAST)
    assert west_red > east_red
    assert west_blue < east_blue
    # And it is the sun that does it: the same row under no sun is level.
    level = HomeSunset().render(render_ctx(t=0.0), leds)
    assert np.allclose(level[WEST], level[EAST])


def test_turning_north_turns_its_warmth() -> None:
    frame = HomeSunset().render(_sun(2.0, 270.0), _row(north_offset_deg=180.0))

    (west_red, west_blue), (east_red, east_blue) = _warm(frame, WEST), _warm(frame, EAST)
    assert east_red > west_red
    assert east_blue < west_blue


def test_the_sun_moves_the_warmth_with_it_across_the_home() -> None:
    leds = _row()
    effect = HomeSunset()

    rising = effect.render(_sun(2.0, 90.0), leds)  # low in the east
    setting = effect.render(_sun(2.0, 270.0), leds)  # low in the west

    assert rising[EAST, 0] > rising[WEST, 0]
    assert setting[WEST, 0] > setting[EAST, 0]
    assert np.allclose(rising[EAST], setting[WEST])  # the same warmth, at the other side


def test_a_higher_sun_warms_the_west_less_for_it_stands_nearer_overhead() -> None:
    leds, effect = _row(), HomeSunset()

    low = effect.render(_sun(5.0, 270.0), leds)
    high = effect.render(_sun(80.0, 270.0), leds)

    assert not np.array_equal(low, high)
    # Low in the west it is warm there and cool in the east; near overhead it is over the
    # middle, so the two ends come close.
    low_gap = low[WEST, 0] - low[EAST, 0]
    high_gap = high[WEST, 0] - high[EAST, 0]
    assert low_gap > 0.1
    assert 0.0 <= high_gap < low_gap / 3.0


@pytest.mark.parametrize(
    ("elevation", "azimuth"), [(5.0, 270.0), (45.0, 270.0), (80.0, 270.0), (-10.0, 135.0)]
)
def test_the_warmth_stands_at_the_sun_point_of_the_suns_height_and_bearing(
    elevation: float, azimuth: float
) -> None:
    leds = _row(north_offset_deg=30.0)
    sun = sun_point(leds, elevation, azimuth)
    anchored = leds_at(
        [*ROW, *BOX], space=replace(leds.space, anchors={"sun": sun})
    )  # Sunset's anchor, put where the sun is

    home = HomeSunset().render(_sun(elevation, azimuth), leds)
    sunset = SunsetGradient(anchor="sun").render(render_ctx(t=0.0), anchored)

    assert np.array_equal(home, sunset)


@pytest.mark.parametrize("t", [0.0, 7.5, 31.0])
def test_without_a_sun_it_plays_as_sunset_with_no_anchor(t: float) -> None:
    settings = {"warmth": 0.8, "level": 0.6, "drift_s": 30.0}
    leds = leds_at(ROW + BOX, anchors={"window": (0.0, 1.0, 1.0)})  # an anchor to ignore

    home = HomeSunset(**settings).render(render_ctx(t=t), leds)
    sunset = SunsetGradient(anchor="", **settings).render(render_ctx(t=t), leds)

    assert np.array_equal(home, sunset)


def test_a_sun_leaves_what_is_kept_for_the_leds_as_it_was() -> None:
    leds = _row()
    effect = HomeSunset()

    first = effect.render(render_ctx(t=0.0), leds)
    effect.render(_sun(2.0, 270.0), leds)  # a frame with a sun, on the same LEDs

    assert np.array_equal(effect.render(render_ctx(t=0.0), leds), first)


def test_the_height_is_worked_out_once_for_the_leds_and_the_sun_every_frame(
    call_counts: CallCounts,
) -> None:
    call_counts.spy(HomeSunset, "_height")
    call_counts.spy(home_sunset, "reach")
    leds, effect = _row(), HomeSunset()

    for azimuth in (270.0, 271.0, 272.0):
        effect.render(_sun(2.0, azimuth), leds)

    assert call_counts.calls == {"_height": 1, "reach": 3}


def test_home_sunset_has_sunsets_settings_but_no_anchor() -> None:
    sunset = SunsetGradient.parameters()
    home = HomeSunset.parameters()

    assert "anchor" in sunset and "anchor" not in home
    assert list(home) == [name for name in sunset if name != "anchor"]
    assert all(home[name] == sunset[name] for name in home)
    assert HomeSunset().get_params().keys() == home.keys()
    with pytest.raises(TypeError, match="no setting anchor"):
        HomeSunset(anchor="window")


def test_home_sunset_is_registered_as_a_field_effect_of_its_own() -> None:
    assert get_effect_class("home_sunset") is HomeSunset
    assert issubclass(HomeSunset, FieldEffect)


HOMES: dict[str, Callable[[], LedSet]] = {"a row": _row, "this home": seeded_ledset}


@pytest.mark.parametrize("home", HOMES)
def test_home_sunset_is_finite_in_range_and_moves_with_the_sun(home: str) -> None:
    leds, effect = HOMES[home](), HomeSunset()

    for elevation in (-20.0, 0.0, 45.0):
        frame = effect.render(_sun(elevation, 270.0), leds)
        assert frame.shape == (leds.count, 3) and frame.dtype == np.float32
        assert np.isfinite(frame).all()
        assert frame.min() >= 0.0 and frame.max() <= 1.0

    here = effect.render(_sun(10.0, 270.0), leds)
    there = effect.render(_sun(10.0, 280.0), leds)  # ten degrees on
    assert not np.array_equal(here, there)


def test_a_frame_with_no_extent_or_no_leds_still_renders() -> None:
    for points in ([(1.0, 1.0, 1.0)], [(0.0, 1.0, 1.0), (4.0, 1.0, 1.0)], []):
        leds = leds_at(points)
        frame = HomeSunset().render(_sun(5.0, 90.0), leds)

        assert frame.shape == (len(points), 3)
        assert np.isfinite(frame).all()
        assert np.isfinite(sun_point(leds, 5.0, 90.0)).all()


@pytest.mark.parametrize("signals", [{SUN_ELEVATION: float("nan"), SUN_AZIMUTH: 270.0}, {}])
def test_a_sun_it_cannot_place_is_no_sun(signals: dict[str, float]) -> None:
    leds = _row()
    ctx = replace(render_ctx(t=0.0), signals=SignalView(signals))

    assert np.array_equal(
        HomeSunset().render(ctx, leds), SunsetGradient(anchor="").render(render_ctx(t=0.0), leds)
    )
