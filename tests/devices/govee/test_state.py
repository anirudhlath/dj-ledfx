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
