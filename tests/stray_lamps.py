"""Lamps that the map, or a layer's transform, puts outside the floor-to-ceiling band, for the
particle effects that run along a lamp (embers, rain, snow, fireflies, spotlights).

Particles stay between the floor and the ceiling, widened for each lamp to take in its own
LEDs: a run's overhang past a lamp stops at the floor or the ceiling, but a lamp's own extent
is never cut, and a lamp the map puts under the floor or over the ceiling still has particles
moving over all of its LEDs.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from conftest import render_ctx, tempo_ctx
from map_home import lights_at, upright
from numpy.typing import NDArray

from dj_ledfx.effects.context import RenderContext
from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.particle_tools import Ground
from dj_ledfx.effects.particles import ParticleEffect

REACH_M = 0.15  # a particle that comes within this height of an LED has passed it


def lowered(leds: LedSet, metres: float) -> LedSet:
    """The set as a layer's transform with a z offset of `metres` shows it: each LED looks
    that far lower."""
    return leds.moved(leds.pos - np.array([0.0, 0.0, metres], dtype=np.float32))


# One upright lamp each, from 0.1 to 1.4 m where the map has put it as it is (the last).
STRAYS: dict[str, LedSet] = {
    "under the floor": lights_at(upright(1.0, 1.0, -1.0, -0.5)),
    "over the ceiling": lights_at(upright(1.0, 1.0, 3.2, 3.5), ceiling=3.0),
    "straddling the floor": lights_at(upright(1.0, 1.0, -0.9, 0.4)),
    "straddling the ceiling": lights_at(upright(1.0, 1.0, 2.5, 3.5), ceiling=3.0),
    "moved down by a transform": lowered(lights_at(upright(1.0, 1.0)), 2.0),
}


def on_the_beat(t: float) -> RenderContext:
    """The moment `t` seconds in, with the beat counted at a steady 120 BPM: for the looks
    that move with the beat count, which render_ctx's frozen beat would leave standing."""
    return tempo_ctx(2.0 * t)


def run_heights(
    effect: ParticleEffect,
    leds: LedSet,
    seconds: float = 30.0,
    step: float = 0.05,
    moment: Callable[[float], RenderContext] = lambda t: render_ctx(t=t),
) -> NDArray[np.float64]:
    """The height of every particle the effect makes over `seconds`, seen every `step`, at
    the moments `moment` makes of the time (render_ctx's, or on_the_beat's)."""
    effect.place(leds)
    seen = []
    for t in np.arange(500.0, 500.0 + seconds, step):
        effect.step(moment(float(t)))
        seen.append(effect.particles.pos[:, 2].astype(np.float64))
    return np.concatenate(seen)


def unpassed(z: NDArray[np.float64], leds: LedSet) -> list[float]:
    """The heights of the LEDs that no particle of a run (the heights z) came within REACH_M
    of: none, for particles that run the whole length of the lamp."""
    heights = np.unique(leds.pos[:, 2].astype(np.float64))
    gaps = np.abs(z[:, None] - heights[None, :]).min(axis=0)
    return [round(float(h), 2) for h in heights[gaps > REACH_M]]


def stays_in_band(z: NDArray[np.float64], leds: LedSet) -> bool:
    """Whether the heights z are between the floor and the ceiling, widened to take in the
    lamp's own LEDs where it stands outside them (not further: the overhang past a lamp
    still stops at the floor and at the ceiling)."""
    ground = Ground.of(leds)
    lamp = leds.pos[:, 2].astype(np.float64)
    eps = 1e-5
    return bool(
        z.min() >= min(ground.floor, lamp.min()) - eps
        and z.max() <= max(ground.ceiling, lamp.max()) + eps
    )
