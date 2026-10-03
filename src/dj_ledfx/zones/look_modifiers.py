"""A look's modifiers (spec §5.3): the downbeat flash, trails (so a flash leaves one), the
evening and the brightness cap. The runtime applies them to the zone's frame after its
layers, in that order, each one making a new array, so a frame the ring holds never
changes."""

from __future__ import annotations

import math
from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.context import EVENING
from dj_ledfx.tempo.model import BEATS_PER_BAR
from dj_ledfx.types import clamp01

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.types import FloatRGB

TRAILS_FALL = 3.0  # a trail fades by e^-3, to 5%, over the look's trail time
FLASH_BEATS = 0.5  # the downbeat flash fades out over half a beat
FLASH_LEVEL = 0.8  # how far towards white the flash starts
EVENING_TINT = (1.0, 0.77, 0.54)  # warm white (about 3500 K) against the look's own white
EVENING_LEVEL = 0.75  # the look's brightness at the evening's fullest
# What the evening multiplies each channel by at its fullest.
EVENING_FULLEST = np.asarray(EVENING_TINT, dtype=np.float32) * np.float32(EVENING_LEVEL)
EVENING_FULLEST.flags.writeable = False


class Trails:
    """Per-LED decay: each LED shows the brighter of the look's colour and its own last
    colour fading, channel by channel, so a light that drops leaves a trail. It keeps a
    copy of what it showed, so nothing after it can change its memory."""

    def __init__(self) -> None:
        self._held: FloatRGB | None = None
        self._at = 0.0

    def reset(self) -> None:
        self._held = None

    def copy(self) -> Trails:
        """These trails as they are now: a twin's (the frame it holds is never changed)."""
        twin = Trails()
        twin._held, twin._at = self._held, self._at
        return twin

    def apply(self, frame: FloatRGB, t: float, trails_s: float) -> FloatRGB:
        held, gap = self._held, max(t - self._at, 0.0)  # a shorter horizon: no time passed
        if held is not None and held.shape == frame.shape and gap < trails_s:
            fading = held * np.float32(math.exp(-TRAILS_FALL * gap / trails_s))
            frame = np.maximum(frame, fading)
        self._held, self._at = frame.copy(), t
        return frame


def flashed(frame: FloatRGB, ctx: RenderContext) -> FloatRGB:
    """A flash towards white on the first beat of every bar, fading over FLASH_BEATS."""
    since = ctx.bar_phase * BEATS_PER_BAR  # beats since the bar began
    if since >= FLASH_BEATS:
        return frame
    amount = np.float32(FLASH_LEVEL * (1.0 - since / FLASH_BEATS) ** 2)
    flashed: FloatRGB = frame + np.maximum(1.0 - frame, 0.0) * amount
    return flashed


def warmed(frame: FloatRGB, ctx: RenderContext) -> FloatRGB:
    """Warmer and dimmer by the evening's amount (the frame's EVENING signal), 0 (day) to 1
    (its fullest)."""
    amount = ctx.signals.get(EVENING)
    if amount <= 0.0:
        return frame
    warmed: FloatRGB = frame * _evening_factor(clamp01(amount))
    return warmed


@lru_cache(maxsize=4)
def _evening_factor(amount: float) -> NDArray[np.float32]:
    """Each channel's factor at this much evening, which moves at most once a second."""
    factor = (1.0 + (EVENING_FULLEST - 1.0) * np.float32(amount)).astype(np.float32)
    factor.flags.writeable = False
    return factor


def capped(frame: FloatRGB, cap: float) -> FloatRGB:
    """Each LED no brighter than the cap, its hue kept: a colour whose brightest channel
    is over the cap is scaled down until that channel is at it."""
    peak = frame.max(axis=1, keepdims=True)
    scale = np.minimum(1.0, np.float32(cap) / np.maximum(peak, np.float32(1e-6)))
    limited: FloatRGB = frame * scale.astype(np.float32)
    return limited
