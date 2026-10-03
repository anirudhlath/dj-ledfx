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


def test_a_route_blends_its_slice_of_the_frames_either_side_of_its_moment() -> None:
    ring = RingBuffer(capacity=4)
    ring.write(_frame(np.zeros((5, 3), dtype=np.float32), 10.0))
    ring.write(_frame(np.eye(5, 3, dtype=np.float32), 11.0))  # LED i full in channel i
    out = ring_route(ring, start=1, stop=3).colors_at(10.25, 2)
    assert out is not None and out.tolist() == [[0, 64, 0], [0, 0, 64]]  # a quarter of 255


# A light's moment moves by less than a frame each time its latency is measured again, and
# the event loop wakes its send loop a millisecond early or late. Sent the nearest frame, a
# light whose moments fell near half-way between frames was sent one frame twice and then
# skipped the next: the bulbs' judder.
def test_a_light_sent_a_frame_on_each_time_steps_evenly_however_its_moments_jitter() -> None:
    ring = RingBuffer(capacity=40)
    for k in range(30):  # red rises 6 levels a frame
        ring.write(_frame(np.full((1, 3), k * 6 / 255, dtype=np.float32), 10.0 + k / 60))
    route = ring_route(ring, start=0, stop=1)
    reds = []
    for j in range(28):
        out = route.colors_at(10.0 + (j + 0.5) / 60 + (0.001 if j % 2 else -0.001), 1)
        assert out is not None
        reds.append(int(out[0, 0]))
    assert np.diff(reds).tolist() == [6] * 27


def test_a_route_never_reads_past_the_end_of_a_frame() -> None:
    ring = RingBuffer(capacity=4)
    ring.write(_frame(np.zeros((2, 3), dtype=np.float32), 1.0))
    assert ring_route(ring, start=1, stop=3).colors_at(1.0, 2) is None
    ring.write(_frame(np.zeros((2, 3), dtype=np.float32), 2.0))
    assert ring_route(ring, start=1, stop=3).colors_at(1.5, 2) is None  # between the two
    assert ring_route(RingBuffer(4), start=0, stop=2).colors_at(1.0, 2) is None


def test_a_slice_is_scaled_before_it_is_converted() -> None:
    colors = np.full((2, 3), 1.0, dtype=np.float32)
    out = slice_colors(colors, 0, 2, 2, scale=0.5)
    assert out is not None and out.tolist() == [[128, 128, 128], [128, 128, 128]]


def test_a_route_sends_its_slice_at_the_zone_s_brightness() -> None:
    ring = RingBuffer(capacity=4)
    ring.write(_frame(np.full((3, 3), 0.8, dtype=np.float32), 10.0))
    ring.write(_frame(np.full((3, 3), 0.4, dtype=np.float32), 11.0))
    route = ring_route(ring, start=0, stop=3, brightness=0.5)
    on_a_frame, between = route.colors_at(10.0, 3), route.colors_at(10.25, 3)
    assert on_a_frame is not None and on_a_frame.tolist() == [[102] * 3] * 3  # 0.4 of 255
    assert between is not None and between.tolist() == [[89] * 3] * 3  # 0.35 of 255
    kept = ring.find_nearest(10.0)
    assert kept is not None and np.allclose(kept.colors, 0.8)  # the ring keeps the full level
