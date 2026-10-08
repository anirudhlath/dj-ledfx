from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pytest
from conftest import tempo_ctx
from map_home import bulbs, lights_at, upright
from stray_lamps import STRAYS, on_the_beat, run_heights, stays_in_band, unpassed

from dj_ledfx.effects import beat_bursts as bursts_module
from dj_ledfx.effects import particle_tools
from dj_ledfx.effects.beat_bursts import ARRIVE, SCATTER_M, BeatBursts
from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.particle_tools import Ground, Lamps
from dj_ledfx.effects.particles import MAX_PARTICLES, drawn

TV = np.array([2.0, 0.2, 1.0], dtype=np.float32)


def _room() -> LedSet:
    """Four upright lamps round a 4 x 4 m room, with a TV anchor on its north wall."""
    corners = (upright(0.5, 0.5), upright(3.5, 0.5), upright(3.5, 3.5), upright(0.5, 3.5))
    return lights_at(*corners, anchors={"tv": TV})


def _bursts(**settings: object) -> BeatBursts:
    bursts = BeatBursts(anchor="tv", **settings)
    bursts.reseed(1)
    return bursts


def _at_the_tv(bursts: BeatBursts) -> int:
    return int((np.linalg.norm(bursts.particles.pos - TV, axis=1) < 1e-5).sum())


def test_every_beat_fires_a_burst_from_the_anchor_and_the_downbeat_a_bigger_one() -> None:
    room = _room()
    bursts = _bursts(per_beat=12, downbeat=2.5)
    drawn(bursts, tempo_ctx(2001.0), room)  # beat 2001: the bar's second
    assert _at_the_tv(bursts) == 12
    drawn(bursts, tempo_ctx(2004.0), room)  # beat 2004: a downbeat
    assert _at_the_tv(bursts) == 30
    assert [bursts.burst_size(beat) for beat in range(2000, 2005)] == [30, 12, 12, 12, 30]


def test_each_particle_lands_on_an_led_of_a_lamp_and_every_lamp_gets_some() -> None:
    room = _room()
    bursts = _bursts(per_beat=12, fade_beats=1.5)
    lamps = set()
    for beat in range(2001, 2009):
        drawn(bursts, tempo_ctx(beat + 0.7), room)  # landed: its burst is 0.7 beats old
        landed = bursts.particles.pos[bursts.particles.count - bursts.burst_size(beat) :]
        gaps = np.linalg.norm(landed[:, None, :] - room.pos[None, :, :], axis=2)
        assert (gaps.min(axis=1) <= SCATTER_M + 1e-5).all()
        lamps |= set((gaps.argmin(axis=1) // 14).tolist())
    assert lamps == {0, 1, 2, 3}


def test_a_particle_lands_within_a_scatter_of_its_led_and_no_further() -> None:
    room = _room()
    bursts = _bursts(per_beat=30)
    gaps = []
    for beat in range(2001, 2009):
        drawn(bursts, tempo_ctx(beat + 0.7), room)  # landed
        landed = bursts.particles.pos[bursts.particles.count - bursts.burst_size(beat) :]
        gaps.append(np.linalg.norm(landed[:, None, :] - room.pos[None, :, :], axis=2).min(axis=1))
    reach = np.concatenate(gaps)
    assert reach.max() <= 0.15 + 1e-5  # the scatter is 0.15 m, a ball round the LED
    assert reach.max() > 0.1  # and some land well out in it
    assert 0.06 < reach.mean() < 0.12  # most of a ball's volume is out toward its edge


def test_the_particles_of_a_burst_and_the_bursts_of_a_bar_each_land_in_places_of_their_own() -> (
    None
):
    room = _room()
    bursts = _bursts(per_beat=30)
    seen = []
    for beat in range(2001, 2009):
        drawn(bursts, tempo_ctx(beat + 0.7), room)
        landed = bursts.particles.pos[bursts.particles.count - bursts.burst_size(beat) :]
        assert len(np.unique(landed, axis=0)) == len(landed)  # no two particles alike
        seen.append(landed)
    for before, after in zip(seen, seen[1:], strict=False):
        both = min(len(before), len(after))
        assert not np.allclose(before[:both], after[:both], atol=1e-3)  # nor two beats' bursts


def test_a_burst_fades_by_fade_beats() -> None:
    room = _room()
    bursts = _bursts(per_beat=12, fade_beats=1.5, palette=["#ffffff"])
    drawn(bursts, tempo_ctx(2001.49), room)
    assert bursts.particles.count == 30 + 12  # the downbeat's burst, and beat 2001's
    assert (bursts.particles.colour[:30, 0] < 0.01).all()  # the downbeat's has all but faded
    drawn(bursts, tempo_ctx(2001.5), room)
    assert bursts.particles.count == 12  # and now it's gone


def test_a_burst_keeps_its_shape_at_any_tempo() -> None:
    room = _room()
    slow, fast = _bursts(), _bursts()
    drawn(slow, tempo_ctx(2001.3, bpm=60.0), room)
    drawn(fast, tempo_ctx(2001.3, bpm=240.0), room)
    np.testing.assert_array_equal(slow.particles.pos, fast.particles.pos)


def test_a_particle_flies_out_fast_and_slows_to_land_arrive_of_the_way_through_its_fade() -> None:
    room = _room()
    bursts = _bursts(per_beat=12, fade_beats=2.0)

    def newest(beats: float) -> np.ndarray:
        drawn(bursts, tempo_ctx(beats), room)
        return bursts.particles.pos[-12:].astype(np.float64)  # beat 2001's burst

    landed = newest(2001.0 + ARRIVE * 2.0)  # a fade of 2 beats: it lands 0.8 of a beat in
    np.testing.assert_array_equal(newest(2001.95), landed)  # and stays where it landed
    half_way = newest(2001.0 + ARRIVE)  # half of that: 3/4 of the way there, slowing
    np.testing.assert_allclose(half_way - TV, 0.75 * (landed - TV), atol=1e-5)
    np.testing.assert_allclose(newest(2001.0), np.repeat([TV], 12, axis=0), atol=1e-5)


def test_a_bursts_colour_is_the_palettes_colour_for_its_beat_round_and_round() -> None:
    room = _room()
    bursts = _bursts(palette=["#ff0000", "#00ff00", "#0000ff"], fade_beats=1.0)
    for beat in range(2001, 2008):
        drawn(bursts, tempo_ctx(float(beat)), room)  # on the beat: the new burst, at full glow
        size = bursts.burst_size(beat)
        assert bursts.particles.count == size
        np.testing.assert_allclose(
            bursts.particles.colour, np.tile(np.eye(3)[beat % 3], (size, 1))
        )


def test_the_particles_are_as_big_as_the_setting_says() -> None:
    bursts = _bursts(size=0.4)
    drawn(bursts, tempo_ctx(2001.3), _room())
    np.testing.assert_allclose(bursts.particles.radius, 0.4)


@pytest.mark.parametrize("anchor", ["", "gone"], ids=["none set", "not on the map"])
def test_with_no_anchor_a_burst_leaves_the_middle_of_the_zone(anchor: str) -> None:
    room = _room()
    bursts = BeatBursts(anchor=anchor, per_beat=12)
    bursts.reseed(1)
    drawn(bursts, tempo_ctx(2001.0), room)
    at_the_middle = np.linalg.norm(bursts.particles.pos - room.centre, axis=1) < 1e-5
    assert int(at_the_middle.sum()) == 12


def test_a_zone_with_no_burst_in_the_air_draws_nothing_and_nothing_breaks() -> None:
    room = _room()
    bursts = _bursts(fade_beats=0.25)
    drawn(bursts, tempo_ctx(2001.1), room)
    assert bursts.particles.count == 12  # 0.1 of a beat old
    frame = drawn(bursts, tempo_ctx(2001.6), room)  # a quarter of a beat is long gone
    assert bursts.particles.count == 0
    assert frame.shape == (room.count, 3) and not frame.any()


def test_a_burst_effect_has_at_most_per_beat_times_downbeat_over_fade_beats_alive() -> None:
    """Four beats are in the air at the longest fade, one of them the downbeat's: 3 * 30 + 120.
    That holds at any tempo and with any number of lamps, since a burst's lamps are picked
    from the draws and not shared out."""
    biggest = {"per_beat": 30, "downbeat": 4.0, "fade_beats": 4.0}
    worst = 3 * 30 + round(30 * 4.0)
    assert worst <= MAX_PARTICLES
    for leds in (bulbs(100), _room()):
        bursts, ground = BeatBursts(**biggest), Ground.of(leds)
        counts = {
            bursts.positions(tempo_ctx(2000.0 + beat, bpm=bpm), ground).count
            for beat in np.arange(0.0, 16.0, 0.07)
            for bpm in (30.0, 300.0)
        }
        assert counts == {worst}


@pytest.mark.parametrize("where", STRAYS)
def test_bursts_land_on_every_led_of_a_lamp_outside_the_floor_and_ceiling(where: str) -> None:
    leds = STRAYS[where]
    z = run_heights(_bursts(), leds, moment=on_the_beat)
    assert np.ptp(z) > 0.1  # moving, not stuck in place
    assert unpassed(z, leds) == []  # landing along the lamp's whole length
    assert stays_in_band(z, leds)  # the scatter round an LED stops at the floor and the ceiling


def test_the_scatter_round_an_led_stops_at_the_floor_and_the_ceiling() -> None:
    edges = lights_at(upright(1.0, 1.0, 0.0, 1.0), upright(2.0, 1.0, 2.0, 3.0))  # floor to ceiling
    z = run_heights(_bursts(per_beat=30), edges, moment=on_the_beat)
    assert z.min() == 0.0 and z.max() == 3.0  # on the floor and on the ceiling, and not past


def test_every_burst_is_worked_out_at_once_however_many_are_in_the_air(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, int] = {}

    def counted(name: str, original: Callable[..., Any]) -> Callable[..., Any]:
        def call(*args: Any, **kwargs: Any) -> Any:
            calls[name] = calls.get(name, 0) + 1
            return original(*args, **kwargs)

        return call

    monkeypatch.setattr(bursts_module, "draws", counted("draws", particle_tools.draws))
    monkeypatch.setattr(Ground, "on", counted("on", Ground.on))
    monkeypatch.setattr(Lamps, "pick", counted("pick", Lamps.pick))

    drawn(_bursts(fade_beats=4.0), tempo_ctx(2003.5), _room())  # four bursts in the air

    assert calls == {"draws": 1, "pick": 1, "on": 1}
