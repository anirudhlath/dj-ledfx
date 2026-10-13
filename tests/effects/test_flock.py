from __future__ import annotations

import numpy as np
from conftest import tempo_ctx
from map_home import lights_at, upright

from dj_ledfx.effects.flock import Flock
from dj_ledfx.effects.particles import drawn

# Four upright lamps at the corners of a 4 x 4 m room.
ROOM = lights_at(upright(0.5, 0.5), upright(3.5, 0.5), upright(3.5, 3.5), upright(0.5, 3.5))


def _flock(**settings: object) -> Flock:
    flock = Flock(**settings)
    flock.reseed(1)
    return flock


def _spread(flock: Flock, beats: float) -> float:
    """How far the birds are from their middle, on average, seen from above, at this moment.
    Seen from above: the flock's height is fitted to the room over and under it, which a
    middle near the floor squeezes, but how far it spreads sideways is `scattered` alone."""
    drawn(flock, tempo_ctx(beats), ROOM)
    pos = flock.particles.pos[:, :2]
    return float(np.linalg.norm(pos - pos.mean(axis=0), axis=1).mean())


def test_the_flock_gathers_round_an_led_of_each_lamp_in_turn() -> None:
    flock = _flock(spread_m=0.2)
    lamps = []
    for bar in range(500, 512, 2):  # it comes to a lamp on every other downbeat
        drawn(flock, tempo_ctx(4.0 * bar), ROOM)
        gaps = np.linalg.norm(flock.particles.pos[:, None, :] - ROOM.pos[None, :, :], axis=2)
        led = int(gaps.max(axis=0).argmin())  # the LED every bird is nearest together
        assert gaps[:, led].max() <= 0.2 + 1e-5
        lamps.append(led // 14)
    assert all(a != b for a, b in zip(lamps, lamps[1:], strict=False))
    assert set(lamps) == {0, 1, 2, 3}


def test_the_flock_scatters_on_every_other_downbeat_and_gathers_again() -> None:
    flock = _flock(scatter=3.0)
    gathered = _spread(flock, 2000.0)  # beat 2000: it has just come to a lamp
    np.testing.assert_allclose(_spread(flock, 2000.75), 3.0 * gathered, rtol=1e-4)
    assert _spread(flock, 2003.0) < 1.5 * gathered  # gathering again by the bar's end
    assert _spread(flock, 2004.75) < 1.2 * gathered  # the bar between: no scatter


def test_the_flock_moves_on_the_beat_at_any_tempo() -> None:
    slow, fast = _flock(), _flock()
    for beats in (2000.0, 2001.3, 2006.9):
        drawn(slow, tempo_ctx(beats, bpm=30.0), ROOM)
        drawn(fast, tempo_ctx(beats, bpm=300.0), ROOM)
        np.testing.assert_array_equal(slow.particles.pos, fast.particles.pos)
