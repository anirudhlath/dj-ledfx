from __future__ import annotations

import numpy as np
from conftest import ring_route

from dj_ledfx.effects.ring_buffer import RingBuffer
from dj_ledfx.scheduling.route import slice_colors, to_device_colors
from dj_ledfx.types import RenderedFrame


def _frame(colors: np.ndarray, t: float) -> RenderedFrame:
    return RenderedFrame(colors=colors, target_time=t, beat_phase=0.0, bar_phase=0.0)


def test_to_device_colors_clamps_rounds_and_fits_the_device() -> None:
    colors = np.array([[-0.5, 0.5, 1.5], [0.2, 0.2, 0.2]], dtype=np.float32)
    out = to_device_colors(colors, 3)
    assert out.dtype == np.uint8
    assert out.tolist() == [[0, 128, 255], [51, 51, 51], [0, 0, 0]]
    assert to_device_colors(colors, 1).tolist() == [[0, 128, 255]]


def test_a_slice_of_a_frame_shorter_than_the_led_set_is_none() -> None:
    colors = np.zeros((2, 3), dtype=np.float32)
    assert slice_colors(colors, 1, 3, 2) is None
    out = slice_colors(colors, 0, 2, 4)
    assert out is not None and out.shape == (4, 3)


def test_a_route_reads_its_slice_of_the_nearest_frame() -> None:
    ring = RingBuffer(capacity=4)
    colors = np.linspace(0.0, 1.0, 15, dtype=np.float32).reshape(5, 3)
    ring.write(_frame(colors, 10.0))
    ring.write(_frame(np.zeros((5, 3), dtype=np.float32), 11.0))
    route = ring_route(ring, start=1, stop=3)
    out = route.colors_at(10.1, 2)
    assert out is not None
    assert out.tolist() == to_device_colors(colors[1:3], 2).tolist()


def test_a_route_never_reads_past_the_end_of_a_frame() -> None:
    ring = RingBuffer(capacity=4)
    ring.write(_frame(np.zeros((2, 3), dtype=np.float32), 1.0))
    assert ring_route(ring, start=1, stop=3).colors_at(1.0, 2) is None
    assert ring_route(RingBuffer(4), start=0, stop=2).colors_at(1.0, 2) is None
