from __future__ import annotations

import numpy as np
from conftest import tempo_ctx
from map_home import lights_at, upright

from dj_ledfx.effects.beat_bursts import SCATTER_M, BeatBursts
from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.particles import drawn

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
