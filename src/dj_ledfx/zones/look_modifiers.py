"""A look's modifiers (spec §5.3): trails, the downbeat flash, the evening and the
brightness cap. The runtime applies them to the zone's frame after its layers, in that
order, each one making a new array, so a frame the ring holds never changes."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.tempo.model import BEATS_PER_BAR

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.types import FloatRGB

TRAILS_FALL = 3.0  # a trail fades by e^-3, to 5%, over the look's trail time
FLASH_BEATS = 0.5  # the downbeat flash fades out over half a beat
FLASH_LEVEL = 0.8  # how far towards white the flash starts
EVENING_TINT = (1.0, 0.77, 0.54)  # warm white (about 3500 K) against the look's own white
EVENING_LEVEL = 0.75  # the look's brightness at the evening's fullest


class Trails:
    """Per-LED decay: each LED shows the brighter of the look's colour and its own last
    colour fading, channel by channel, so a light that drops leaves a trail. It keeps a
    copy of what it showed, so nothing after it can change its memory."""

    def __init__(self) -> None:
        self._held: FloatRGB | None = None
        self._at = 0.0

    def reset(self) -> None:
        self._held = None

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


def warmed(frame: FloatRGB, amount: float) -> FloatRGB:
    """Warmer and dimmer by the evening's amount, 0 (day) to 1 (its fullest)."""
    if amount <= 0.0:
        return frame
    fullest = np.asarray(EVENING_TINT, dtype=np.float32) * np.float32(EVENING_LEVEL)
    factor = 1.0 + (fullest - 1.0) * np.float32(min(amount, 1.0))
    warmed: FloatRGB = frame * factor
    return warmed


def capped(frame: FloatRGB, cap: float) -> FloatRGB:
    """Each LED no brighter than the cap, its hue kept: a colour whose brightest channel
    is over the cap is scaled down until that channel is at it."""
    peak = frame.max(axis=1, keepdims=True)
    scale = np.minimum(1.0, np.float32(cap) / np.maximum(peak, np.float32(1e-6)))
    limited: FloatRGB = frame * scale.astype(np.float32)
    return limited
