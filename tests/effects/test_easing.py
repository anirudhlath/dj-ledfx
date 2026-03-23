import numpy as np
import pytest

from dj_ledfx.effects.easing import ease_in, ease_in_out, ease_out, lerp, sine_ease


def test_lerp_endpoints():
    assert lerp(0.0, 10.0, 0.0) == 0.0
    assert lerp(0.0, 10.0, 1.0) == 10.0


def test_lerp_midpoint():
    assert lerp(0.0, 10.0, 0.5) == pytest.approx(5.0)


def test_lerp_numpy_array():
    t = np.array([0.0, 0.5, 1.0])
    result = lerp(0.0, 10.0, t)
    np.testing.assert_allclose(result, [0.0, 5.0, 10.0])


def test_ease_in_endpoints():
    assert ease_in(0.0) == pytest.approx(0.0)
    assert ease_in(1.0) == pytest.approx(1.0)


def test_ease_in_is_slow_at_start():
    assert ease_in(0.5) < 0.5


def test_ease_out_endpoints():
    assert ease_out(0.0) == pytest.approx(0.0)
    assert ease_out(1.0) == pytest.approx(1.0)


def test_ease_out_is_fast_at_start():
    assert ease_out(0.5) > 0.5


def test_ease_in_out_endpoints():
    assert ease_in_out(0.0) == pytest.approx(0.0)
    assert ease_in_out(1.0) == pytest.approx(1.0)


def test_ease_in_out_midpoint():
    assert ease_in_out(0.5) == pytest.approx(0.5)


def test_sine_ease_endpoints():
    assert sine_ease(0.0) == pytest.approx(0.0)
    assert sine_ease(1.0) == pytest.approx(1.0)


def test_sine_ease_numpy_array():
    t = np.array([0.0, 1.0])
    result = sine_ease(t)
    np.testing.assert_allclose(result, [0.0, 1.0], atol=1e-10)
