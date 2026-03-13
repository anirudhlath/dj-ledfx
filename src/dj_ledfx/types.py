from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

RGB = tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    name: str
    device_type: str
    led_count: int
    address: str


@dataclass(slots=True)
class RenderedFrame:
    colors: NDArray[np.uint8]  # shape (n_leds, 3)
    target_time: float  # monotonic time when this should be displayed
    beat_phase: float
    bar_phase: float


@dataclass(frozen=True, slots=True)
class BeatState:
    beat_phase: float  # 0.0 → 1.0
    bar_phase: float  # 0.0 → 1.0
    bpm: float
    is_playing: bool
    next_beat_time: float  # monotonic timestamp


@dataclass(frozen=True, slots=True)
class DeviceStats:
    """Per-device send statistics snapshot."""

    device_name: str
    effective_latency_ms: float
    send_fps: float
    frames_dropped: int
