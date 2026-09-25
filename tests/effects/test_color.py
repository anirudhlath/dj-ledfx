import numpy as np
import pytest

from dj_ledfx.effects.color import hex_to_rgb, hsv_to_rgb_array, palette_lerp, rgb_to_hex


def test_hex_to_rgb():
    assert hex_to_rgb("#ff0000") == (255, 0, 0)
    assert hex_to_rgb("#00ff00") == (0, 255, 0)
    assert hex_to_rgb("0000ff") == (0, 0, 255)


def test_rgb_to_hex():
    assert rgb_to_hex(255, 0, 0) == "#ff0000"
    assert rgb_to_hex(0, 255, 0) == "#00ff00"


def test_hsv_to_rgb_array_red():
    h = np.array([0.0])
    result = hsv_to_rgb_array(h, 1.0, 1.0)
    assert result.shape == (1, 3)
    assert result.dtype == np.uint8
    assert result[0, 0] == 255  # R
    assert result[0, 1] == 0  # G
    assert result[0, 2] == 0  # B


def test_hsv_to_rgb_array_rainbow():
    h = np.array([0.0, 1 / 3, 2 / 3])
    result = hsv_to_rgb_array(h, 1.0, 1.0)
    assert result.shape == (3, 3)
    # Red
    assert result[0, 0] == 255
    # Green
    assert result[1, 1] == 255
    # Blue
    assert result[2, 2] == 255


def test_hsv_to_rgb_array_value_scales():
    h = np.array([0.0])
    result = hsv_to_rgb_array(h, 1.0, 0.5)
    assert result[0, 0] == 127 or result[0, 0] == 128  # ~half brightness


def test_palette_lerp_endpoints():
    palette = [(255, 0, 0), (0, 0, 255)]
    positions = np.array([0.0, 1.0])
    result = palette_lerp(palette, positions)
    assert result.shape == (2, 3)
    assert result.dtype == np.uint8
    np.testing.assert_array_equal(result[0], [255, 0, 0])
    np.testing.assert_array_equal(result[1], [0, 0, 255])


def test_palette_lerp_midpoint():
    palette = [(0, 0, 0), (200, 200, 200)]
    positions = np.array([0.5])
    result = palette_lerp(palette, positions)
    assert result[0, 0] == pytest.approx(100, abs=1)


def test_palette_lerp_wraps():
    palette = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    positions = np.array([0.0, 0.5, 1.0])
    result = palette_lerp(palette, positions)
    assert result.shape == (3, 3)


def test_palette_lerp_single_color():
    palette = [(128, 64, 32)]
    positions = np.array([0.0, 0.5, 1.0])
    result = palette_lerp(palette, positions)
    for i in range(3):
        np.testing.assert_array_equal(result[i], [128, 64, 32])


def test_the_8_bit_colours_stay_within_1_of_exact_maths() -> None:
    """Ruling: merging the float and 8-bit formulas may move a channel by at most 1."""
    import colorsys

    rng = np.random.default_rng(3)
    hues, sats, vals = rng.random(500), rng.random(500), rng.random(500)
    exact = np.array(
        [colorsys.hsv_to_rgb(h, s, v) for h, s, v in zip(hues, sats, vals, strict=True)]
    )
    got = hsv_to_rgb_array(hues, sats, vals).astype(int)
    assert np.abs(got - np.floor(exact * 255.0)).max() <= 1

    palette = [(255, 0, 0), (0, 200, 90), (30, 60, 250)]
    positions = rng.random(500)
    stops = np.array(palette, dtype=np.float64)
    at = np.linspace(0.0, 1.0, len(palette))
    exact = np.stack([np.interp(positions, at, stops[:, c]) for c in range(3)], axis=1)
    assert np.abs(palette_lerp(palette, positions).astype(int) - np.floor(exact)).max() <= 1
    np.testing.assert_array_equal(palette_lerp(palette, at), palette)  # stops stay exact
