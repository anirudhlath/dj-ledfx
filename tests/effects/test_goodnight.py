"""Goodnight's field (looks.json "goodnight", M6 ruling 9): a warm glow walks the home, rooms
switching off farthest first from the night room, which is left on a night light. Every frame
is a function of the look's elapsed time, never of the clock."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from types import MappingProxyType
from typing import Any

import numpy as np
import pytest
from conftest import CallCounts, render_ctx

from dj_ledfx.effects.color import palette_float
from dj_ledfx.effects.field import FieldEffect
from dj_ledfx.effects.goodnight import FADE_S, FRONT_BOOST, FRONT_S, OFF_AFTER_S, Goodnight
from dj_ledfx.effects.ledset import (
    NO_ROOM,
    LedSet,
    LedSource,
    Outline,
    PlacedLeds,
    Space,
    build_ledset,
)
from dj_ledfx.effects.registry import get_effect_class

WALK = 30.0
ROOMS = ("west", "middle", "east")  # in a row, 4 m square each, from the west
PARAMS = Goodnight.parameters()
PALETTE = palette_float(PARAMS["palette"].default)
LEVEL, NIGHT_LEVEL = float(PARAMS["level"].default), float(PARAMS["night_level"].default)
REST = PALETTE[0] * np.float32(LEVEL)  # what a room glows until the front is near


def _square(x: float) -> Outline:
    return ((x, 0.0), (x + 4.0, 0.0), (x + 4.0, 4.0), (x, 4.0))


def _space(outlines: Mapping[str, Outline] | None = None) -> Space:
    shapes = outlines or {room: _square(4.0 * index) for index, room in enumerate(ROOMS)}
    return Space(rooms=tuple(shapes), room_outlines=MappingProxyType(dict(shapes)), ceiling=3.0)


def _leds(rooms: Sequence[int], space: Space | None = None) -> LedSet:
    """One light of two LEDs in each of these rooms (an index into the space's rooms, NO_ROOM
    for none), in order: the light k has LEDs 2k and 2k + 1."""
    sources = []
    for index, room in enumerate(rooms):
        x = 4.0 * room + 1.0 if room != NO_ROOM else -3.0
        points = np.array([[x, 2.0, 1.0], [x + 1.0, 2.0, 1.0]])
        placed = PlacedLeds.from_positions(points)
        sources.append(LedSource(f"light-{index}", 2, placed=placed, room=room))
    return build_ledset(sources, space or _space())


THREE = _leds([0, 1, 2])
WEST, MIDDLE, EAST = slice(0, 2), slice(2, 4), slice(4, 6)
FIRST, SECOND = WALK / 3.0, 2.0 * WALK / 3.0  # the east room's switch, then the middle's


def _goodnight(**settings: Any) -> Goodnight:
    return Goodnight(**{"night_room": "west", "walk_s": WALK, **settings})


def _frame(effect: Goodnight, leds: LedSet, elapsed: float) -> np.ndarray:
    return effect.render(replace(render_ctx(t=1000.0), elapsed_s=elapsed), leds)


def _lit(frame: np.ndarray) -> bool:
    return bool((frame.max(axis=1) > 0.0).all())


def test_goodnight_has_the_settings_the_plan_gives_it() -> None:
    assert list(PARAMS) == ["walk_s", "night_room", "night_level", "palette", "level"]
    assert [(p.type, p.default, p.min, p.max) for p in PARAMS.values()] == [
        ("float", 60.0, 10.0, 600.0),
        ("zone", "", None, None),
        ("float", 0.12, 0.0, 1.0),
        ("color_list", PARAMS["palette"].default, None, None),
        ("float", 0.7, 0.0, 1.0),
    ]
    assert len(PALETTE) == 2 and PALETTE[1].sum() > PALETTE[0].sum()  # the brighter: the front
    assert (FRONT_BOOST, FRONT_S, FADE_S) == (1.4, 3.0, 2.0)
    assert get_effect_class("goodnight") is Goodnight
    assert issubclass(Goodnight, FieldEffect)


def test_every_room_glows_warm_at_the_start() -> None:
    frame = _frame(_goodnight(), THREE, 0.0)

    assert frame.shape == (6, 3) and frame.dtype == np.float32
    assert np.allclose(frame, REST)
    assert (frame[:, 0] > frame[:, 1]).all() and (frame[:, 1] > frame[:, 2]).all()  # warm


def test_rooms_switch_off_farthest_from_the_night_room_first() -> None:
    goodnight = _goodnight()

    east_gone = _frame(goodnight, THREE, FIRST + FADE_S)
    assert not east_gone[EAST].any()
    assert _lit(east_gone[MIDDLE]) and _lit(east_gone[WEST])  # the middle's turn is later
    middle_gone = _frame(goodnight, THREE, SECOND + FADE_S)
    assert not middle_gone[EAST].any() and not middle_gone[MIDDLE].any()
    assert _lit(middle_gone[WEST])  # the night room stays
    before = _frame(goodnight, THREE, FIRST - FRONT_S - 0.01)
    assert np.allclose(before, REST)  # nothing has begun


def test_rooms_are_ordered_by_the_distance_between_their_centres() -> None:
    # The night room's centre is (2, 2). The long room's vertices crowd its west end, so their
    # mean is about 6.7 m from it, nearer than the square's centre (8 m), but the long room's
    # own centre is 11 m away: farthest by its centre, not by its vertices.
    crowded = tuple((6.0 + 0.1 * step, 0.0) for step in range(10))
    long_room = (*crowded, (20.0, 0.0), (20.0, 4.0), (6.0, 4.0))
    outlines = {"west": _square(0.0), "square": _square(8.0), "long": long_room}
    leds = _leds([0, 1, 2], _space(outlines))  # one light in each; the east slice is the long

    frame = _frame(_goodnight(), leds, FIRST + FADE_S)

    assert not frame[EAST].any()  # the long room, the farthest by its centre, went first
    assert _lit(frame[MIDDLE]) and _lit(frame[WEST])


def test_each_room_brightens_as_the_front_reaches_it_then_goes_black() -> None:
    goodnight = _goodnight()

    for room, switch in ((EAST, FIRST), (MIDDLE, SECOND)):
        times = np.linspace(0.0, switch + FADE_S + 1.0, 521)
        glow = np.array([_frame(goodnight, THREE, t)[room][0].sum() for t in times])

        peak = times[glow.argmax()]
        assert switch - FRONT_S - 1e-6 <= peak <= switch + 1e-6  # as the front arrives
        assert glow.max() > glow[0]  # brighter than its start level
        assert np.allclose(glow[times < switch - FRONT_S - 1e-6], glow[0])  # flat before it
        assert (np.diff(glow[times <= switch]) >= -1e-6).all()  # rising into the switch
        half = _frame(goodnight, THREE, switch + FADE_S / 2.0)[room]
        assert _lit(half) and half[0].sum() < glow.max()  # half-way down: lit, but dimmer
        assert not _frame(goodnight, THREE, switch + FADE_S)[room].any()  # black after FADE_S
        assert not _frame(goodnight, THREE, switch + 5.0)[room].any()  # and stays so


def test_the_front_boosts_the_glow_by_its_factor_and_never_past_full() -> None:
    brightest = _frame(_goodnight(), THREE, FIRST)[EAST][0]  # at the switch, before the fade
    boosted = PALETTE[1] * np.float32(LEVEL * FRONT_BOOST)

    assert np.allclose(brightest, np.minimum(boosted, 1.0))
    assert (boosted <= 1.0).all()  # the default level leaves room for the boost
    full = _goodnight(level=1.0)
    frames = np.stack([_frame(full, THREE, t) for t in np.linspace(0.0, 40.0, 161)])
    assert frames.max() == 1.0 and frames.min() == 0.0  # clipped to one, black when off
    assert np.isfinite(frames).all() and frames.dtype == np.float32


def test_the_night_room_settles_on_its_night_light_and_stays() -> None:
    for night_level in (NIGHT_LEVEL, 0.3):
        goodnight = _goodnight(night_level=night_level)
        night_light = PALETTE[0] * np.float32(night_level)

        for elapsed in (WALK, WALK * 10.0):
            frame = _frame(goodnight, THREE, elapsed)
            assert np.allclose(frame[WEST], night_light)
            assert not frame[MIDDLE].any() and not frame[EAST].any()
        # It glows as it did until the last room's switch, then eases over that room's share.
        assert np.allclose(_frame(goodnight, THREE, SECOND)[WEST], REST)
        halfway = PALETTE[0] * np.float32((LEVEL + night_level) / 2.0)
        assert np.allclose(_frame(goodnight, THREE, (SECOND + WALK) / 2.0)[WEST], halfway)


def test_leds_in_no_room_go_dark_with_the_first_room() -> None:
    leds = _leds([0, 1, 2, NO_ROOM])
    goodnight = _goodnight()
    no_room = slice(6, 8)

    for elapsed in (0.0, 5.0, 8.5, 9.9, FIRST, 11.0, FIRST + FADE_S, 15.0):
        frame = _frame(goodnight, leds, elapsed)
        assert np.array_equal(frame[no_room], frame[EAST])  # step for step with the east room
    frame = _frame(goodnight, leds, FIRST + FADE_S)
    assert not frame[no_room].any() and _lit(frame[MIDDLE])


@pytest.mark.parametrize("night_room", ["attic", ""])
def test_a_night_room_not_on_the_map_walks_every_room_off(night_room: str) -> None:
    goodnight = _goodnight(night_room=night_room)
    moments = [WALK * n / 4.0 for n in (1, 2, 3)]  # three rooms to switch off

    assert np.allclose(_frame(goodnight, THREE, 0.0), REST)
    one_gone = _frame(goodnight, THREE, moments[0] + FADE_S)
    assert [not one_gone[room].any() for room in (WEST, MIDDLE, EAST)].count(True) == 1
    for elapsed in (moments[2] + FADE_S, WALK, WALK * 10.0):
        assert not _frame(goodnight, THREE, elapsed).any()  # no room is left on


def test_a_night_room_with_no_lights_in_the_zone_walks_every_room_off() -> None:
    leds = _leds([1, 2])  # the middle and east rooms: the west, the night room, has none

    assert np.allclose(_frame(_goodnight(), leds, 0.0), REST)
    assert not _frame(_goodnight(), leds, WALK).any()


def test_lights_in_no_room_at_all_go_dark_together_half_way() -> None:
    leds = _leds([NO_ROOM, NO_ROOM], Space(ceiling=3.0))  # a zone on no map
    goodnight = _goodnight()

    assert np.allclose(_frame(goodnight, leds, WALK / 2.0 - FRONT_S - 0.01), REST)
    assert not _frame(goodnight, leds, WALK / 2.0 + FADE_S).any()
    assert not _frame(goodnight, leds, WALK * 10.0).any()


def test_goodnight_is_a_function_of_its_elapsed_time() -> None:
    goodnight = _goodnight()
    first = goodnight.render(replace(render_ctx(t=5.0), elapsed_s=12.0), THREE)
    later = goodnight.render(replace(render_ctx(t=9000.0), elapsed_s=12.0), THREE)
    other = goodnight.render(replace(render_ctx(t=5.0), elapsed_s=21.0), THREE)

    assert np.array_equal(first, later)
    assert not np.array_equal(first, other)


def test_a_look_that_has_not_begun_draws_its_start() -> None:
    goodnight = _goodnight()

    assert np.array_equal(_frame(goodnight, THREE, -5.0), _frame(goodnight, THREE, 0.0))


def test_a_changed_setting_moves_the_walk() -> None:
    goodnight = _goodnight()
    assert not _frame(goodnight, THREE, FIRST + FADE_S)[EAST].any()

    goodnight.set_params(walk_s=2.0 * WALK)  # the east room's turn is now at 20 s
    assert _lit(_frame(goodnight, THREE, FIRST + FADE_S)[EAST])
    assert not _frame(goodnight, THREE, 2.0 * FIRST + FADE_S)[EAST].any()

    goodnight.set_params(night_room="east")  # and the east room is the one left on
    assert _lit(_frame(goodnight, THREE, 2.0 * WALK)[EAST])
    assert not _frame(goodnight, THREE, 2.0 * WALK)[WEST].any()


def test_the_walk_is_worked_out_once_for_a_set_of_leds(call_counts: CallCounts) -> None:
    call_counts.spy(Goodnight, "_walk")
    goodnight = _goodnight()

    for elapsed in (0.0, 4.0, 9.0, 12.0):
        _frame(goodnight, THREE, elapsed)
    assert call_counts.calls == {"_walk": 1}
    _frame(goodnight, _leds([0, 1, 2]), 0.0)  # other LEDs: the order and moments again
    assert call_counts.calls == {"_walk": 2}


def test_lights_out_is_each_rooms_switch_its_fade_and_a_second(call_counts: CallCounts) -> None:
    goodnight = _goodnight()
    call_counts.spy(Goodnight, "_walk")

    _frame(goodnight, THREE, 0.0)
    out = goodnight.lights_out(THREE)
    _frame(goodnight, THREE, 1.0)  # lights_out left the render's slot as it was

    assert out is not None and out.dtype == np.float32 and out.shape == (6,)
    assert np.allclose(out[EAST], FIRST + FADE_S + OFF_AFTER_S)
    assert np.allclose(out[MIDDLE], SECOND + FADE_S + OFF_AFTER_S)
    assert np.isinf(out[WEST]).all()  # the night room is never out
    assert call_counts.calls == {"_walk": 1}  # one builder: the render's walk, never worked twice
    leds = _leds([0, 1, 2, NO_ROOM])  # LEDs in no room go with the east room
    times = goodnight.lights_out(leds)
    assert times is not None and np.allclose(times[6:8], out[EAST])
    for moment in sorted({float(t) + extra for t in times if np.isfinite(t) for extra in (0, 7)}):
        frame = _frame(goodnight, leds, moment)
        out_now = times <= moment
        assert not frame[out_now].any() and _lit(frame[~out_now])
    assert _lit(_frame(goodnight, leds, 10.0 * WALK)[WEST])


def test_a_zone_with_no_leds_draws_no_colours() -> None:
    frame = _frame(_goodnight(), _leds([]), 5.0)

    assert frame.shape == (0, 3) and frame.dtype == np.float32
