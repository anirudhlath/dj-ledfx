from __future__ import annotations

import numpy as np
from conftest import tempo_ctx
from map_home import lights_at, upright

from dj_ledfx.effects.fountain import Fountain
from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.particles import drawn

TABLE = np.array([2.0, 2.0, 0.45], dtype=np.float32)


def _room() -> LedSet:
    """Four upright lamps round a 4 x 4 m room, with a coffee table in its middle."""
    corners = (upright(0.5, 0.5), upright(3.5, 0.5), upright(3.5, 3.5), upright(0.5, 3.5))
    return lights_at(*corners, anchors={"coffee": TABLE})


def _fountain(**settings: object) -> Fountain:
    fountain = Fountain(anchor="coffee", **settings)
    fountain.reseed(1)
    return fountain


def _spray(fountain: Fountain, seconds: float = 4.0) -> np.ndarray:
    """Every drop's place over some seconds at 120 BPM, 30 times a second."""
    room = _room()
    seen = []
    for step in range(int(seconds * 30)):
        drawn(fountain, tempo_ctx(2000.0 + step / 15), room)
        seen.append(fountain.particles.pos)
    return np.concatenate(seen)


def test_the_spray_rises_to_its_height_and_never_falls_under_the_floor() -> None:
    where = _spray(_fountain(burst=0, height_m=1.2))
    assert where[:, 2].min() >= 0.0
    assert 0.85**2 * 1.2 < where[:, 2].max() - TABLE[2] <= 1.2 + 1e-4


def test_the_spray_comes_down_within_its_spread() -> None:
    where = _spray(_fountain(burst=0, spread_m=1.5))
    above = where[where[:, 2] >= TABLE[2]]  # before a drop falls past the table
    away = np.linalg.norm(above[:, :2] - TABLE[:2], axis=1)
    assert away.max() <= 1.5 + 1e-4
    assert away.max() > 1.0
    np.testing.assert_allclose(where[:, :2].mean(axis=0), TABLE[:2], atol=0.3)


def test_every_beat_fires_a_burst_of_drops() -> None:
    room = _room()
    fountain = _fountain(rate=5.0, burst=40)
    drawn(fountain, tempo_ctx(2000.999), room)
    before = fountain.particles.count
    drawn(fountain, tempo_ctx(2001.001), room)
    assert fountain.particles.count - before in (39, 40, 41)  # a spray drop may come or go


def test_a_burst_goes_higher_than_the_spray() -> None:
    sprayed = _spray(_fountain(burst=0))[:, 2].max()
    burst = _spray(_fountain(rate=5.0, burst=60))[:, 2].max()
    assert burst > sprayed + 0.3


def test_a_bursts_drops_land_on_leds_on_the_next_beat() -> None:
    room = _room()
    fountain = _fountain(rate=5.0, burst=8)
    drawn(fountain, tempo_ctx(2001.0), room)
    pos = fountain.particles.pos
    gaps = np.linalg.norm(pos[:, None, :] - room.pos[None, :, :], axis=2).min(axis=1)
    assert (gaps < 1e-4).sum() == 8  # beat 2000's burst, on its LEDs
    # Oldest first: the spray drops thrown since beat 2000's burst come before beat 2001's.
    np.testing.assert_allclose(pos[-8:], np.repeat([TABLE], 8, axis=0), atol=1e-5)  # 2001's
