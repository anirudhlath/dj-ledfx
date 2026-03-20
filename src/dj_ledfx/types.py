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
    mac: str | None = None
    stable_id: str | None = None


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
    pitch_percent: float | None = None
    deck_number: int | None = None
    deck_name: str | None = None


@dataclass(frozen=True, slots=True)
class DeviceStats:
    """Per-device send statistics snapshot."""

    device_name: str
    effective_latency_ms: float
    send_fps: float
    frames_dropped: int
    connected: bool = True


@dataclass(frozen=True, slots=True)
class DeviceGroup:
    name: str
    color: str  # hex color for UI display
