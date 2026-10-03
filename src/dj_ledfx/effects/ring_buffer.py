"""A running zone's rendered frames, ahead of time: the engine writes them, the send loops
read the two either side of each light's own moment, and the web app's feed the nearest."""

from __future__ import annotations

from dj_ledfx.types import RenderedFrame


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

    def find_nearest(self, target_time: float) -> RenderedFrame | None:
        best: RenderedFrame | None = None
        best_diff = float("inf")

        for frame in self._frames:
            if frame is None:
                continue
            diff = abs(frame.target_time - target_time)
            if diff < best_diff:
                best_diff = diff
                best = frame

        # The frame itself: nothing changes a written frame, and a route converts its
        # slice into a new 8-bit array before any send.
        return best

    def find_around(self, target_time: float) -> tuple[RenderedFrame, RenderedFrame, float] | None:
        """The frames either side of target_time, and how far it lies from the first to the
        second, 0 to 1. A moment before the first frame or past the last gets that frame
        alone, at 0; None while the ring is empty. Found by their times, not the order they
        were written in: a horizon that shrinks renders a frame for a moment before frames
        already written."""
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
