import numpy as np
import pytest

from dj_ledfx.types import RGB, BeatState, DeviceInfo, RenderedFrame


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


def test_beat_state() -> None:
    state = BeatState(
        beat_phase=0.25,
        bar_phase=0.0625,
        bpm=128.0,
        is_playing=True,
        next_beat_time=1000.5,
    )
    assert state.bpm == 128.0
    assert state.is_playing is True


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


def test_device_info_frozen():
    info = DeviceInfo(name="Test", device_type="test", led_count=10, address="1.2.3.4:80")
    try:
        info.name = "Changed"  # type: ignore[misc]
        assert False, "Should have raised"
    except AttributeError:
        pass
