from __future__ import annotations

import numpy as np
import pytest
from conftest import CallCounts, render_ctx
from map_home import lights_at, seeded_ledset, upright
from numpy.typing import NDArray
from stray_lamps import STRAYS, moves, run_frames, stays_in_band

from dj_ledfx.effects import wisp as wisp_module
from dj_ledfx.effects.ledset import NO_ROOM, LedSet
from dj_ledfx.effects.particle_tools import REACH, Ground
from dj_ledfx.effects.particles import ParticleEffect, drawn
from dj_ledfx.effects.registry import get_effect_class
from dj_ledfx.effects.wisp import Wisp

# Two rooms, two upright lamps in each: lamps 0 and 1 are in room 0, lamps 2 and 3 in room 1.
TWO_ROOMS = lights_at(
    upright(1.0, 1.0),
    upright(2.5, 3.0),
    upright(6.0, 1.0),
    upright(7.0, 3.0),
    rooms=[0, 0, 1, 1],
)
# Three rooms, one lamp in each, so that a tour has an order to keep.
THREE_ROOMS = lights_at(upright(1.0, 1.0), upright(5.0, 1.0), upright(9.0, 1.0), rooms=[0, 1, 2])
# Three lamps in one room, and the same three on a map that places none of them.
ONE_ROOM = [0, 0, 0]
NO_ROOMS = [NO_ROOM] * 3
THREE_LAMPS = (upright(1.0, 1.0), upright(3.0, 1.0), upright(5.0, 3.0))
HOLD, MOVE = 4.0, 3.0
STEP = HOLD + MOVE
REST = HOLD / STEP  # the share of each step spent resting


def _wisps(**settings: object) -> Wisp:
    wisps = Wisp(**settings)
    wisps.reseed(1)
    return wisps


def _on_an_led(wisps: Wisp, leds: LedSet) -> tuple[NDArray[np.float64], NDArray[np.intp]]:
    """How far each wisp is from the nearest LED, and which LED that is."""
    gap = np.linalg.norm(wisps.particles.pos[:, None, :] - leds.pos[None, :, :], axis=2)
    return gap.min(axis=1), gap.argmin(axis=1)


def _rests(leds: LedSet, steps: range, count: int = 1) -> list[list[int]]:
    """The LED each wisp rests on at the middle of each of these steps of its own."""
    wisps = _wisps(count=count, hold_s=HOLD, move_s=MOVE)
    leds_by_wisp: list[list[int]] = [[] for _ in range(count)]
    for step in steps:
        for k in range(count):
            t = (step + REST / 2.0 - k / count) * STEP  # wisp k's steps start k/count late
            drawn(wisps, render_ctx(t=t), leds)
            distance, nearest = _on_an_led(wisps, leds)
            assert distance[k] < 1e-4  # it rests on an LED
            leds_by_wisp[k].append(int(nearest[k]))
    return leds_by_wisp


def test_wisp_has_the_settings_the_plan_gives_it() -> None:
    params = Wisp.parameters()

    assert list(params) == ["count", "hold_s", "move_s", "size", "palette", "level"]
    assert [(p.type, p.default, p.min, p.max) for p in params.values()] == [
        ("int", 2, 1, 4),
        ("float", 4.0, 0.5, 30.0),
        ("float", 3.0, 0.5, 20.0),
        ("float", 0.5, 0.2, 1.5),
        ("color_list", params["palette"].default, None, None),
        ("float", 0.8, 0.0, 1.0),
    ]
    assert len(params["palette"].default) == 1  # one warm white
    assert get_effect_class("wisp") is Wisp
    assert issubclass(Wisp, ParticleEffect)


@pytest.mark.parametrize("count", [1, 2, 3, 4])
def test_wisp_makes_count_wisps_at_every_moment(count: int) -> None:
    leds = seeded_ledset()
    wisps = _wisps(count=count)
    for t in np.linspace(700.0, 790.0, 20):
        drawn(wisps, render_ctx(t=float(t)), leds)
        assert wisps.particles.count == count


def test_there_are_two_wisps_by_default() -> None:
    wisps = _wisps()
    drawn(wisps, render_ctx(t=700.0), TWO_ROOMS)
    assert wisps.particles.count == 2


@pytest.mark.parametrize("leds", [TWO_ROOMS, THREE_ROOMS], ids=["two rooms", "three rooms"])
def test_a_wisp_rests_on_a_lamps_led_then_moves_to_another_room(leds: LedSet) -> None:
    [rests] = _rests(leds, range(100, 124))

    rooms = [int(leds.room[led]) for led in rests]
    assert all(a != b for a, b in zip(rooms, rooms[1:], strict=False))
    assert set(rooms) == set(range(int(leds.room.max()) + 1))  # every room, in time


def test_every_wisp_rests_on_an_led_of_its_own_in_turn() -> None:
    by_wisp = _rests(TWO_ROOMS, range(100, 112), count=3)

    for rests in by_wisp:
        rooms = [int(TWO_ROOMS.room[led]) for led in rests]
        assert all(a != b for a, b in zip(rooms, rooms[1:], strict=False))


@pytest.mark.parametrize("rooms", [ONE_ROOM, NO_ROOMS], ids=["one room", "no rooms"])
def test_with_one_room_a_wisp_tours_its_lamps(rooms: list[int]) -> None:
    leds = lights_at(*THREE_LAMPS, rooms=rooms)

    [rests] = _rests(leds, range(99, 111))  # four rounds of three steps

    lamps = [led // 14 for led in rests]
    assert all(a != b for a, b in zip(lamps, lamps[1:], strict=False))  # never one twice running
    for start in range(0, len(lamps), 3):
        assert sorted(lamps[start : start + 3]) == [0, 1, 2]  # each lamp once a round


def test_with_one_lamp_a_wisp_stays_on_it() -> None:
    leds = lights_at(upright(2.0, 2.0), rooms=[0])

    [rests] = _rests(leds, range(100, 110))

    assert {led // 14 for led in rests} == {0}


def test_a_lamp_in_no_room_is_never_a_stop_while_the_map_has_rooms() -> None:
    leds = lights_at(
        upright(1.0, 1.0), upright(6.0, 1.0), upright(3.5, 3.0), rooms=[0, 1, NO_ROOM]
    )

    [rests] = _rests(leds, range(100, 140))

    assert {led // 14 for led in rests} == {0, 1}


def test_a_wisp_picks_its_lamp_in_each_room_and_its_led_on_it_from_draws() -> None:
    [rests] = _rests(TWO_ROOMS, range(100, 140))

    assert {led // 14 for led in rests} == {0, 1, 2, 3}  # both lamps of each room
    assert len(set(rests)) > 10  # and a different LED of a lamp each visit


def test_each_lamp_glows_only_while_a_wisp_is_near() -> None:
    wisps = _wisps(count=3, size=0.5)
    far = near = resting = 0
    for t in np.arange(700.0, 760.0, 0.25):
        frame = drawn(wisps, render_ctx(t=float(t)), TWO_ROOMS)
        distance = np.linalg.norm(
            TWO_ROOMS.pos[:, None, :] - wisps.particles.pos[None, :, :], axis=2
        ).min(axis=1)
        out = distance > REACH * 0.5
        on = distance < 1e-4
        assert not frame[out].any()  # past the reach of every wisp: black
        assert (frame[on].max(axis=1) > 0.5).all()  # the LED a wisp rests on: lit
        far, near, resting = (
            far + int(out.sum()),
            near + int((~out).sum()),
            resting + int(on.sum()),
        )
    assert far > 0 and near > 0 and resting > 0  # the test saw dark, glowing and resting LEDs


def test_wisps_set_off_apart() -> None:
    for count in (2, 3, 4):
        wisps = _wisps(count=count, hold_s=HOLD, move_s=MOVE)
        starts = np.zeros(count, dtype=np.int64)
        last = was_moving = None
        for t in np.arange(700.0, 700.0 + 3 * STEP, 1 / 30):  # three steps of each wisp
            drawn(wisps, render_ctx(t=float(t)), TWO_ROOMS)
            pos = wisps.particles.pos.copy()
            if last is not None:
                moving = (pos != last).any(axis=1)
                if was_moving is not None:
                    setting_off = moving & ~was_moving  # at rest in the last frame, gliding now
                    assert setting_off.sum() <= 1  # never two in one frame
                    starts += setting_off
                was_moving = moving
            last = pos
        assert (starts >= 2).all()  # each wisp set off at least twice


def test_a_wisp_rests_for_hold_s_and_glides_for_move_s() -> None:
    wisps = _wisps(count=1, hold_s=5.0, move_s=2.0)  # a step is 7 s, the first from 700 s

    def off_the_leds(t: float) -> float:
        drawn(wisps, render_ctx(t=t), TWO_ROOMS)
        return float(_on_an_led(wisps, TWO_ROOMS)[0][0])

    assert max(off_the_leds(700.0 + s) for s in (0.0, 2.5, 4.9)) < 1e-4  # resting
    assert min(off_the_leds(700.0 + s) for s in (5.5, 6.0, 6.5)) > 0.1  # gliding
    assert off_the_leds(707.0) < 1e-4  # on the next lamp as the next step starts


def test_each_wisp_picks_its_leds_from_draws_of_its_own() -> None:
    one = lights_at(upright(2.0, 2.0), rooms=[0])  # one lamp: the wisps differ by their LEDs
    wisps = _wisps(count=3, hold_s=4.0, move_s=0.5)
    resting = alike = 0
    for t in np.arange(700.0, 1400.0, 0.5):
        drawn(wisps, render_ctx(t=float(t)), one)
        z = wisps.particles.pos[:, 2].astype(np.float64)
        on_led = np.abs(z[:, None] - one.pos[None, :, 2]).min(axis=1) < 1e-4
        for a, b in ((0, 1), (0, 2), (1, 2)):
            if on_led[a] and on_led[b]:  # both rest, each on an LED of the lamp
                resting += 1
                alike += abs(z[a] - z[b]) < 1e-4
    assert resting > 2000
    assert alike < 0.2 * resting  # about one in the lamp's 14 LEDs; from one stream, over half


def test_a_wisp_glides_between_rests_without_a_jump() -> None:
    wisps = _wisps(count=1, hold_s=HOLD, move_s=MOVE)
    last, steps = None, []
    for t in np.arange(700.0, 800.0, 0.05):
        drawn(wisps, render_ctx(t=float(t)), TWO_ROOMS)
        pos = wisps.particles.pos[0].copy()
        if last is not None:
            steps.append(float(np.linalg.norm(pos - last)))
        last = pos
    # Room to room is at most about 6.5 m in 3 s; the glide eases, so at most 1.5 times the
    # mean speed: 0.17 m in a twentieth of a second.
    assert 0.05 < max(steps) < 0.25


def test_a_wisp_sets_off_gently() -> None:
    wisps = _wisps(count=1, hold_s=4.0, move_s=3.0)  # a step is 7 s: rest till 704, glide to 707

    def at(t: float) -> NDArray[np.float32]:
        drawn(wisps, render_ctx(t=t), TWO_ROOMS)
        return wisps.particles.pos[0].copy()

    start = float(np.linalg.norm(at(704.1) - at(704.0)))
    middle = float(np.linalg.norm(at(705.55) - at(705.45)))
    assert middle > 0.1  # a tenth of a second of the room-to-room glide, at its quickest
    assert start < 0.3 * middle


def test_the_settings_reach_the_wisps() -> None:
    wisps = _wisps(count=3, size=1.2, palette=["#ff0000", "#00ff00"], level=0.5)
    drawn(wisps, render_ctx(t=700.0), TWO_ROOMS)

    np.testing.assert_allclose(wisps.particles.radius, 1.2)
    np.testing.assert_allclose(
        wisps.particles.colour, [[0.5, 0, 0], [0, 0.5, 0], [0.5, 0, 0]], atol=1e-6
    )


def test_the_default_wisp_is_a_warm_white_at_the_default_level() -> None:
    wisps = _wisps()
    drawn(wisps, render_ctx(t=700.0), TWO_ROOMS)

    colour = wisps.particles.colour
    np.testing.assert_allclose(colour[0], colour[1])
    red, green, blue = colour[0]
    assert 0.7 < red <= 0.8 + 1e-6  # as bright as the level lets it be
    assert red > green > blue > 0.4  # warm, not coloured: white leaning to amber
    np.testing.assert_allclose(wisps.particles.radius, 0.5)


def test_wisp_is_the_same_moment_however_the_frames_fall() -> None:
    stepped, jumped = _wisps(count=3), _wisps(count=3)
    for t in (700.0, 703.3, 709.9, 731.1):
        drawn(stepped, render_ctx(t=t), TWO_ROOMS)
    moment = render_ctx(t=747.3)

    np.testing.assert_array_equal(
        drawn(stepped, moment, TWO_ROOMS), drawn(jumped, moment, TWO_ROOMS)
    )
    np.testing.assert_array_equal(stepped.particles.pos, jumped.particles.pos)


def test_another_seed_tours_the_rooms_in_another_order() -> None:
    tours = set()
    for seed in (1, 2, 3):
        wisps = Wisp(count=1, hold_s=HOLD, move_s=MOVE)
        wisps.reseed(seed)
        rooms = []
        for step in range(100, 112):
            drawn(wisps, render_ctx(t=(step + REST / 2.0) * STEP), THREE_ROOMS)
            rooms.append(int(THREE_ROOMS.room[_on_an_led(wisps, THREE_ROOMS)[1][0]]))
        tours.add(tuple(rooms))
    assert len(tours) == 3


@pytest.mark.parametrize("where", STRAYS)
def test_wisps_move_along_a_lamp_outside_the_floor_and_ceiling(where: str) -> None:
    leds = STRAYS[where]
    frames = run_frames(_wisps(count=3), leds)
    z = np.concatenate(frames)
    assert moves(frames)  # moving from one of its LEDs to another, frame by frame
    lamp = leds.pos[:, 2]
    assert lamp.min() - 1e-5 <= z.min() and z.max() <= lamp.max() + 1e-5  # on the lamp itself
    assert stays_in_band(z, leds)


def test_every_wisp_is_worked_out_at_once_not_one_after_another(
    call_counts: CallCounts,
) -> None:
    call_counts.spy(wisp_module, "tour")
    call_counts.spy(wisp_module, "draws")
    call_counts.spy(Ground, "on")

    drawn(_wisps(count=4), render_ctx(t=500.0), TWO_ROOMS)

    assert call_counts.calls == {"tour": 1, "draws": 1, "on": 1}
