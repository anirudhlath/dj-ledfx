"""Where a device's frames come from: its zone's ring buffer and its slice (spec §4.1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from dj_ledfx.effects.ring_buffer import RingBuffer
    from dj_ledfx.types import FloatRGB


def to_device_colors(colors: FloatRGB, led_count: int) -> NDArray[np.uint8]:
    """Clamp float RGB and convert it to 8 bits: the one conversion, at send."""
    out = np.zeros((led_count, 3), dtype=np.uint8)
    count = min(led_count, colors.shape[0])
    scaled = np.clip(colors[:count], 0.0, 1.0) * np.float32(255.0) + np.float32(0.5)
    out[:count] = scaled.astype(np.uint8)
    return out


@dataclass(frozen=True, slots=True)
class DeviceRoute:
    ring: RingBuffer
    start: int
    stop: int
    streaming: bool  # False while the light runs a firmware layer itself

    def colors_at(self, target_time: float, led_count: int) -> NDArray[np.uint8] | None:
        """This device's slice of the zone frame nearest target_time, or None."""
        frame = self.ring.find_nearest(target_time)
        if frame is None or frame.colors.shape[0] < self.stop:
            return None
        return to_device_colors(frame.colors[self.start : self.stop], led_count)
