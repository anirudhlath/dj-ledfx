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


def to_device_colors(colors: FloatRGB, led_count: int, scale: float = 1.0) -> NDArray[np.uint8]:
    """Float RGB in 8 bits at a brightness (scale), clamped: the one conversion, at send.
    The brightness folds into the one multiply. Always a new array, padded with black when
    the device has more LEDs than the slice; the frame itself is never changed."""
    count = min(led_count, colors.shape[0])
    levels = colors[:count] * np.float32(255.0 * scale)  # a new array, so clipped in place
    np.clip(levels, 0.0, 255.0, out=levels)
    levels += np.float32(0.5)
    if count == led_count:
        return levels.astype(np.uint8)
    out = np.zeros((led_count, 3), dtype=np.uint8)
    out[:count] = levels.astype(np.uint8)
    return out


def overlaid(base: FloatRGB, scale: float, top: FloatRGB, amount: float) -> FloatRGB:
    """An overlay screened onto a zone's colours (M6 ruling 10): each LED shows z + o - z*o,
    where z is `base` at its brightness (`scale`) and o is `top` at its amount, both held
    to 0..1. It never darkens what's under it. A new array: neither input is written."""
    z = base * np.float32(scale)
    np.clip(z, 0.0, 1.0, out=z)
    o = top * np.float32(amount)
    np.clip(o, 0.0, 1.0, out=o)
    o *= np.float32(1.0) - z
    o += z
    return o


class OverSource(Protocol):
    """What plays over a zone's lights: the zone manager's overlay slot (zones/overlay.py)."""

    def over_at(self, device_id: str, t: float, count: int) -> tuple[FloatRGB, float] | None:
        """The overlay's colours for the light at t, and their amount, or None when nothing
        plays, it doesn't cover the light, its slice isn't `count` LEDs, its ring is empty
        or the amount is 0."""
        ...


class FrameSource(Protocol):
    """What a route reads: a zone's runtime (zones/runtime.py)."""

    @property
    def ring(self) -> RingBuffer: ...

    @property
    def leds(self) -> LedSet: ...

    @property
    def brightness(self) -> float: ...


@dataclass(frozen=True, slots=True)
class DeviceRoute:
    """A device's share of its zone's frames. The zone's ring and the device's slice are
    read at each send, so a zone that rebuilds its LED set keeps its routes."""

    source: FrameSource
    device_id: str
    streaming: bool  # False while the light runs a firmware layer itself
    over: OverSource | None = None  # an overlay mixed in at send, if one plays

    def colors_at(self, target_time: float, led_count: int) -> NDArray[np.uint8] | None:
        """This device's slice of its zone's frames at target_time, blended from the two
        either side of it, in 8 bits, or None."""
        piece = self.source.leds.slice_for(self.device_id)
        if piece is None or piece.count == 0:
            return None
        colors = self.source.ring.colors_at(target_time, piece.start, piece.stop)
        if colors is None:
            return None
        over = (
            None
            if self.over is None
            else self.over.over_at(self.device_id, target_time, colors.shape[0])
        )
        if over is None:
            return to_device_colors(colors, led_count, self.source.brightness)
        mixed = overlaid(colors, self.source.brightness, *over)
        return to_device_colors(mixed, led_count)
