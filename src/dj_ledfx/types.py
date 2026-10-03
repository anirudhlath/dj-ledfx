from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TypeGuard

import numpy as np
from numpy.typing import NDArray

RGB = tuple[int, int, int]
FloatRGB = NDArray[np.float32]  # shape (n_leds, 3), linear 0..1 per channel


def clamp01(value: float) -> float:
    """A brightness or fraction held within 0..1."""
    return max(0.0, min(1.0, value))


def is_finite_number(value: object) -> TypeGuard[int | float]:
    """An int or float that isn't a bool, NaN or infinite, and fits a float: what a setting,
    the map or the tempo takes as a number."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:  # an int too big for a float
        return False


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    name: str
    device_type: str
    led_count: int
    address: str
    mac: str | None = None
    stable_id: str | None = None
    backend: str = ""

    @property
    def effective_id(self) -> str:
        """stable_id if set, otherwise name — used as cross-session device key."""
        return self.stable_id if self.stable_id else self.name


@dataclass(slots=True)
class RenderedFrame:
    colors: FloatRGB  # shape (n_leds, 3), linear 0..1
    target_time: float  # monotonic time when this should be displayed
    beat_phase: float
    bar_phase: float


@dataclass(frozen=True, slots=True)
class BeatContext:
    """The beat as today's 1D effects see it; field effects get the whole RenderContext
    (effects/context.py)."""

    beat_phase: float  # 0.0-1.0 within current beat
    bar_phase: float  # 0.0-1.0 within current 4-beat bar
    bpm: float  # current pitch-adjusted BPM
    dt: float  # frame delta (seconds)
    dj: bool = False  # a DJ's deck drives the tempo (effects/context.py's DJ_BEAT signal)
    beat_index: int = 0  # beats since the tempo clock started counting


@dataclass(frozen=True, slots=True)
class DeviceStats:
    """Per-device send statistics snapshot."""

    device_name: str
    effective_latency_ms: float
    send_fps: float
    frames_dropped: int
    connected: bool = True
    device_id: str = ""  # the light's stable id
    dropped_pct: float = 0.0  # share of frames dropped over the last second, while streaming


@dataclass(frozen=True, slots=True)
class DeviceGroup:
    name: str
    color: str  # hex color for UI display
