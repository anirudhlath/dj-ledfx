"""Where a device's frames come from: its zone's ring buffer and its slice (spec §4.1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.effects.ring_buffer import RingBuffer
    from dj_ledfx.types import FloatRGB


def to_device_colors(colors: FloatRGB, led_count: int) -> NDArray[np.uint8]:
    """Clamp float RGB and convert it to 8 bits: the one conversion, at send. Always a
    new array, padded with black when the device has more LEDs than the slice."""
    count = min(led_count, colors.shape[0])
    scaled = np.clip(colors[:count], 0.0, 1.0) * np.float32(255.0) + np.float32(0.5)
    if count == led_count:
        return scaled.astype(np.uint8)
    out = np.zeros((led_count, 3), dtype=np.uint8)
    out[:count] = scaled.astype(np.uint8)
    return out


def slice_colors(
    colors: FloatRGB, start: int, stop: int, led_count: int
) -> NDArray[np.uint8] | None:
    """LEDs start..stop of a zone frame in 8 bits, for a device of led_count LEDs. None
    when the frame is shorter: it was rendered for an LED set since rebuilt."""
    if colors.shape[0] < stop:
        return None
    return to_device_colors(colors[start:stop], led_count)


class FrameSource(Protocol):
    """What a route reads: a zone's runtime (zones/runtime.py)."""

    @property
    def ring(self) -> RingBuffer: ...

    @property
    def leds(self) -> LedSet: ...


@dataclass(frozen=True, slots=True)
class DeviceRoute:
    """A device's share of its zone's frames. The zone's ring and the device's slice are
    read at each send, so a zone that rebuilds its LED set keeps its routes."""

    source: FrameSource
    device_id: str
    streaming: bool  # False while the light runs a firmware layer itself

    def colors_at(self, target_time: float, led_count: int) -> NDArray[np.uint8] | None:
        """This device's slice of the zone frame nearest target_time, or None."""
        piece = self.source.leds.slice_for(self.device_id)
        if piece is None or piece.count == 0:
            return None
        frame = self.source.ring.find_nearest(target_time)
        if frame is None:
            return None
        return slice_colors(frame.colors, piece.start, piece.stop, led_count)
