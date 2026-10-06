"""Replies for the doze check, on a fake clock: landing at a dozing light's wakes (`on_beat`,
`bunched`), spread evenly round the beacon cycle (`spread`), half at the wakes
(`half_bunched`), or at random moments (`random_moments`)."""

from __future__ import annotations

import math
import random

from dj_ledfx.latency.doze import BEACON_S

START = 1000.0  # when the first reply lands, on the fake clock
PHI = (math.sqrt(5) - 1) / 2  # a phase step that never repeats, so phases spread evenly


def on_beat(k: int) -> float:
    """When the k-th reply lands from a light that answers at every fifth wake."""
    return START + 5 * BEACON_S * k


def bunched(k: int) -> float:
    """As on_beat, give or take 3 ms."""
    return on_beat(k) + 0.003 * ((k % 3) - 1)


def spread(k: int) -> float:
    """About every fifth beacon, each reply at a new phase: spread evenly round the cycle."""
    return START + (5 * k + (k * PHI) % 1.0) * BEACON_S


def half_bunched(k: int) -> float:
    """Every other reply at the wake, the rest a quarter or three quarters of the way round:
    bunched less than a dozing light's replies, and more than chance's."""
    if k % 2 == 0:
        return on_beat(k)
    return START + (5 * k + (0.25 if (k // 2) % 2 == 0 else 0.75)) * BEACON_S


def random_moments(seed: int, count: int = 40) -> list[float]:
    """Replies 0.375–0.625 s apart at random, as the Govee probe loop's waits put them."""
    rng = random.Random(seed)
    moments: list[float] = []
    arrived = START
    for _ in range(count):
        arrived += rng.uniform(0.375, 0.625)
        moments.append(arrived)
    return moments
