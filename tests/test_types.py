import numpy as np

from dj_ledfx.types import RGB, BeatContext, DeviceInfo, RenderedFrame, is_finite_number


def test_rgb_type_alias() -> None:
    color: RGB = (255, 0, 128)
    assert len(color) == 3


def test_device_info() -> None:
    info = DeviceInfo(
        name="Test LED",
        device_type="openrgb",
        led_count=60,
        address="127.0.0.1:6742",
    )
    assert info.name == "Test LED"
    assert info.led_count == 60


def test_rendered_frame() -> None:
    colors = np.zeros((10, 3), dtype=np.uint8)
    frame = RenderedFrame(
        colors=colors,
        target_time=1000.0,
        beat_phase=0.5,
        bar_phase=0.125,
    )
    assert frame.colors.shape == (10, 3)
    assert frame.target_time == 1000.0


def test_device_info_defaults_backward_compatible():
    """Existing 4-arg construction still works."""
    info = DeviceInfo(name="Test", device_type="test", led_count=10, address="1.2.3.4:80")
    assert info.mac is None
    assert info.stable_id is None


def test_device_info_with_mac_and_stable_id():
    info = DeviceInfo(
        name="LIFX Strip (192.168.1.5)",
        device_type="lifx_strip",
        led_count=60,
        address="192.168.1.5:56700",
        mac="d073d5aabbcc",
        stable_id="lifx:d073d5aabbcc",
    )
    assert info.mac == "d073d5aabbcc"
    assert info.stable_id == "lifx:d073d5aabbcc"


def test_beat_context_creation():
    ctx = BeatContext(beat_phase=0.5, bar_phase=0.25, bpm=128.0, dt=0.016)
    assert ctx.beat_phase == 0.5
    assert ctx.bar_phase == 0.25
    assert ctx.bpm == 128.0
    assert ctx.dt == 0.016


def test_beat_context_is_frozen():
    import pytest

    ctx = BeatContext(beat_phase=0.5, bar_phase=0.25, bpm=128.0, dt=0.016)
    with pytest.raises(AttributeError):
        ctx.bpm = 130.0


def test_device_info_frozen():
    info = DeviceInfo(name="Test", device_type="test", led_count=10, address="1.2.3.4:80")
    try:
        info.name = "Changed"  # type: ignore[misc]
        raise AssertionError("Should have raised")
    except AttributeError:
        pass


def test_a_finite_number_is_an_int_or_float_that_fits_a_float() -> None:
    assert is_finite_number(3) and is_finite_number(-2.5)
    for value in (float("nan"), float("inf"), True, "3", None, 10**400):
        assert not is_finite_number(value), value
