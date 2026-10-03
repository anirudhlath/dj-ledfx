from dj_ledfx.devices.govee.state import GoveeDeviceState


def test_roundtrip_serialization():
    state = GoveeDeviceState(on_off=0, brightness=50, r=100, g=200, b=50)
    data = state.to_bytes()
    restored = GoveeDeviceState.from_bytes(data)
    assert restored == state


def test_from_status():
    status = {"onOff": 0, "brightness": 75, "color": {"r": 10, "g": 20, "b": 30}}
    state = GoveeDeviceState.from_status(status)
    assert state.on_off == 0
    assert state.brightness == 75
    assert state.r == 10
    assert state.g == 20
    assert state.b == 30


def test_from_status_defaults():
    state = GoveeDeviceState.from_status({})
    assert state.on_off == 1
    assert state.brightness == 100
    assert state.r == 255
    assert state.g == 255
    assert state.b == 255


def test_from_bytes_with_partial_data():
    import json

    data = json.dumps({"onOff": 1}).encode("utf-8")
    state = GoveeDeviceState.from_bytes(data)
    assert state.on_off == 1
    assert state.brightness == 100
    assert state.r == 255


WARM_WHITE = {
    "onOff": 1,
    "brightness": 80,
    "color": {"r": 0, "g": 0, "b": 0},
    "colorTemInKelvin": 2700,
}


def test_a_lamp_on_white_is_captured_with_its_colour_temperature():
    """On white, a lamp's colour means nothing (black from one lamp, white from another): the
    white is its colour temperature."""
    state = GoveeDeviceState.from_status(WARM_WHITE)
    assert state.kelvin == 2700
    assert GoveeDeviceState.from_bytes(state.to_bytes()) == state


def test_a_capture_without_a_colour_temperature_is_a_colour():
    import json

    data = json.dumps({"onOff": 1, "color": {"r": 1, "g": 2, "b": 3}}).encode("utf-8")
    assert GoveeDeviceState.from_bytes(data).kelvin == 0
