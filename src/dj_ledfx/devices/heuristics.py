from __future__ import annotations


def estimate_device_latency_ms(device_name: str) -> float:
    """Map device name to initial latency estimate (ms).

    Govee WiFi: ~100ms, LIFX WiFi: ~50ms, everything else: ~5ms (USB/wired assumed).
    """
    name_lower = device_name.lower()
    if "govee" in name_lower:
        return 100.0
    if "lifx" in name_lower:
        return 50.0
    return 5.0
