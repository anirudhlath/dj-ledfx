from dj_ledfx.devices.heuristics import estimate_device_latency_ms


def test_govee_device() -> None:
    assert estimate_device_latency_ms("Govee H6061") == 100.0


def test_lifx_device() -> None:
    assert estimate_device_latency_ms("LIFX Strip") == 50.0


def test_unknown_device_defaults_to_usb() -> None:
    assert estimate_device_latency_ms("Corsair RGB") == 5.0


def test_case_insensitive() -> None:
    assert estimate_device_latency_ms("GoVeE") == 100.0
    assert estimate_device_latency_ms("lifx") == 50.0


def test_empty_string() -> None:
    assert estimate_device_latency_ms("") == 5.0


def test_govee_takes_priority_over_lifx() -> None:
    assert estimate_device_latency_ms("Govee-LIFX-Bridge") == 100.0
