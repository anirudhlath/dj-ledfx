from __future__ import annotations

import itertools

import numpy as np
from conftest import render_ctx
from map_home import leds_at

from dj_ledfx.effects.lava_plasma import LavaPlasma

ROOM = [(x * 0.5, y * 1.0, 0.2 + 0.6 * y) for x in range(8) for y in range(3)]


def _lava(seed: int = 4) -> LavaPlasma:
    effect = LavaPlasma()
    effect.reseed(seed)
    return effect


def test_lava_stays_in_lava_colours() -> None:
    leds = leds_at(ROOM)
    effect = _lava()
    for t in np.arange(0.0, 120.0, 7.5):
        frame = effect.render(render_ctx(t=float(t)), leds)
        assert np.all(frame[:, 0] >= frame[:, 1]) and np.all(frame[:, 1] >= frame[:, 2])


def test_lava_moves_slowly() -> None:
    leds = leds_at(ROOM)
    effect = _lava()

    now = effect.render(render_ctx(t=500.0), leds)

    assert np.abs(effect.render(render_ctx(t=500.0 + 1 / 60), leds) - now).max() < 0.05
    assert np.abs(effect.render(render_ctx(t=530.0), leds) - now).max() > 0.1


def test_lava_never_quite_repeats() -> None:
    leds = leds_at(ROOM)
    effect = _lava()

    frames = [effect.render(render_ctx(t=97.0 * step), leds) for step in range(60)]

    for a, b in itertools.combinations(frames, 2):
        assert np.abs(a - b).max() > 1e-3
    assert np.array_equal(frames[5], _lava().render(render_ctx(t=97.0 * 5), leds))
