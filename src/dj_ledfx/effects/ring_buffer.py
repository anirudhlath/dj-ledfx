"""A running zone's rendered frames, ahead of time: the engine writes them, and the send
loops and the web app's feed read the colours at a moment, blended from the frames either
side of it."""

from __future__ import annotations

from dj_ledfx.effects.easing import lerp
from dj_ledfx.types import FloatRGB, RenderedFrame


class RingBuffer:
    def __init__(self, capacity: int) -> None:
        self._capacity = capacity
        self._frames: list[RenderedFrame | None] = [None] * capacity
        self._write_index = 0
        self._count = 0

    @property
    def count(self) -> int:
        return self._count

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def fill_level(self) -> float:
        return self._count / self._capacity

    def write(self, frame: RenderedFrame) -> None:
        self._frames[self._write_index] = frame
        self._write_index = (self._write_index + 1) % self._capacity
        if self._count < self._capacity:
            self._count += 1

    def find_around(self, target_time: float) -> tuple[RenderedFrame, RenderedFrame, float] | None:
        """The frames either side of target_time, and how far it lies from the first to the
        second, 0 to 1. A moment before the first frame or past the last gets that frame
        alone, at 0; None while the ring is empty. Found by their times, not where they sit
        in the ring: the ring wraps, and a horizon that shrinks renders a frame for a moment
        before frames already written."""
        before: RenderedFrame | None = None
        after: RenderedFrame | None = None
        before_t, after_t = float("-inf"), float("inf")
        for frame in self._frames:
            if frame is None:
                continue
            t = frame.target_time
            if t <= target_time:
                if t > before_t:
                    before, before_t = frame, t
            elif t < after_t:
                after, after_t = frame, t
        if before is None:
            return None if after is None else (after, after, 0.0)
        if after is None:
            return before, before, 0.0
        return before, after, (target_time - before_t) / (after_t - before_t)

    def colors_at(self, target_time: float, start: int, stop: int) -> FloatRGB | None:
        """LEDs start..stop at target_time, blended from the frames either side of it, or
        None: the ring is empty, or a frame is shorter than stop. Between two frames it's a
        new array; on a frame or outside them, that frame's own colours, since nothing
        changes a written frame and readers convert into a new array."""
        found = self.find_around(target_time)
        if found is None:
            return None
        first, second, weight = found
        if min(first.colors.shape[0], second.colors.shape[0]) < stop:
            return None
        colors = first.colors[start:stop]
        return lerp(colors, second.colors[start:stop], weight) if weight > 0.0 else colors
