import pytest

from dj_ledfx.effects.energy import bpm_energy


def test_below_low_is_zero():
    assert bpm_energy(80.0) == 0.0


def test_above_high_is_one():
    assert bpm_energy(170.0) == 1.0


def test_at_low_boundary():
    assert bpm_energy(100.0) == pytest.approx(0.0)


def test_at_high_boundary():
    assert bpm_energy(150.0) == pytest.approx(1.0)


def test_midpoint():
    assert bpm_energy(125.0) == pytest.approx(0.5)


def test_custom_range():
    assert bpm_energy(140.0, low=120.0, high=160.0) == pytest.approx(0.5)


def test_zero_bpm():
    assert bpm_energy(0.0) == 0.0
