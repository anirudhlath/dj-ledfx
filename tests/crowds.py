"""A crowd of lamps dealt its worst hand, for the effects that make particles lamp by lamp
(embers and rain).

Such an effect keeps to the particle cap by arithmetic: a lamp's events are born one in each
stretch, so only so many of them can overlap, and the lamps share the cap between them. A
seeded run never comes near that limit, so a test that only counts a run's particles can't
tell an effect that keeps to the cap from one that doesn't. This deals the draws the worst
way instead: in each lamp's stream the older events are born as late in their stretches as
they can be and the newer as early, so that they crowd together, and (with `lives`) each
lives as long as it can.
"""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

import numpy as np
import pytest
from conftest import render_ctx
from numpy.typing import ArrayLike, NDArray

from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.particle_tools import LAMP_KEYS, Ground, draws
from dj_ledfx.effects.particles import ParamParticles

LATE = 1.0 - 1e-9  # the latest a draw can be, short of 1
SPLITS = 3  # where the crowding falls among a lamp's events depends on the moment: try these


def dealt(split: int, *, lives: bool = False) -> Callable[..., NDArray[np.float64]]:
    """draws() with the worst hand dealt. Stream 0 is a lamp's events, event n of lamp s from
    key n * LAMP_KEYS + s (birth in column 0, the length of the life in column 1); stream 1
    is the rain's strikes, strike n from key n. Where the older events fall among the newer
    depends on the moment, so a test tries a few `split`s."""

    def deal(seed: int, keys: ArrayLike, count: int, stream: int = 0) -> NDArray[np.float64]:
        u = draws(seed, keys, count, stream)
        if len(u) and stream in (0, 1):
            n = np.asarray(keys, dtype=np.int64)
            n = n // LAMP_KEYS if stream == 0 else n
            u[:, 0] = np.where(n < (n.min() + n.max() + split) // 2, LATE, 0.0)  # late, or early
            if lives and stream == 0:
                u[:, 1] = LATE  # the longest life
        return u

    return deal


def worst_crowd(
    monkeypatch: pytest.MonkeyPatch,
    module: ModuleType,
    effect: ParamParticles,
    leds: LedSet,
    seconds: float,
    *,
    lives: bool = False,
) -> tuple[int, int]:
    """Run `effect` on a row of bulbs a metre apart (map_home.bulbs) for `seconds`, with the
    draws `module` makes dealt the worst way: how many bulbs ever have a particle near them,
    and the most one has at once. Particles an effect makes before step() cuts them to the
    cap; those over a metre wide (the rain's strikes) are left out."""
    ground, seen, most = Ground.of(leds), set[int](), 0
    effect.place(leds)
    for split in range(SPLITS):
        monkeypatch.setattr(module, "draws", dealt(split, lives=lives))
        for t in np.linspace(500.0, 500.0 + seconds, 200):
            made = effect.positions(render_ctx(t=float(t)), ground)
            near = np.rint(made.pos[made.radius < 1.0, 0]).astype(np.int64)
            counts = np.bincount(near, minlength=1)
            most = max(most, int(counts.max()))
            seen.update(np.flatnonzero(counts).tolist())
    return len(seen), most
