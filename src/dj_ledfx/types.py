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
    backend: str = ""

    @property
    def effective_id(self) -> str:
        """stable_id if set, otherwise name — used as cross-session device key."""
        return self.stable_id if self.stable_id else self.name


@dataclass(slots=True)
class RenderedFrame:
    colors: NDArray[np.uint8]  # shape (n_leds, 3)
    target_time: float  # monotonic time when this should be displayed
    beat_phase: float
    bar_phase: float


@dataclass(frozen=True, slots=True)
class BeatContext:
    """Minimal beat state for effect rendering. Intentionally strips transport
    fields from BeatState (is_playing, next_beat_time, etc.) to keep the
    effect API narrow."""

    beat_phase: float  # 0.0-1.0 within current beat
    bar_phase: float  # 0.0-1.0 within current 4-beat bar
    bpm: float  # current pitch-adjusted BPM
    dt: float  # frame delta (seconds)


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
