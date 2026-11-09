"""The ring's one unblended read: the frame at a moment, for what it draws in space."""

from __future__ import annotations

import numpy as np

from dj_ledfx.effects.ring_buffer import RingBuffer
from dj_ledfx.types import RenderedFrame


def _frame(t: float) -> RenderedFrame:
    return RenderedFrame(
        colors=np.zeros((1, 3), dtype=np.float32), target_time=t, beat_phase=0.0, bar_phase=0.0
    )


def test_frame_at_is_the_newest_frame_at_or_before_the_moment_never_a_blend() -> None:
    ring = RingBuffer(3)
    assert ring.frame_at(1.0) is None  # empty
    frames = [_frame(t) for t in (1.0, 2.0, 3.0, 4.0)]  # the ring wraps: 1.0 goes
    for frame in frames:
        ring.write(frame)

    assert ring.frame_at(2.0) is frames[1]  # on a frame: that frame
    assert ring.frame_at(2.9) is frames[1]  # between two: the one before, held
    assert ring.frame_at(9.0) is frames[3]  # past the newest: the newest
    assert ring.frame_at(0.5) is frames[1]  # before the first: the first, as colors_at holds it
