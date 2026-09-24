"""Spec §9: each zone renders in under 5 ms on this home's 412 LEDs. Run with -m perf."""

from __future__ import annotations

import statistics
import time

import pytest

from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.looks.builtin import builtin_looks
from dj_ledfx.looks.model import Look
from dj_ledfx.zones.runtime import ZoneLight, ZoneRuntime

pytestmark = pytest.mark.perf

CANDLE = DeviceCapabilities(protocol="LIFX", matrix=True, chain=True)
NEON = DeviceCapabilities(protocol="LIFX", multizone=True, extended_multizone=True)
BULB = DeviceCapabilities(protocol="LIFX")
LAMP = DeviceCapabilities(protocol="Govee")
PC = DeviceCapabilities(protocol="OpenRGB", openrgb_modes=("Direct", "Rainbow Wave"))

HOME = [
    *[(30, CANDLE)] * 3,
    (52, CANDLE),
    *[(1, BULB)] * 9,
    (65, NEON),
    (20, LAMP),
    *[(10, PC)] * 4,
    (1, PC),
    (1, PC),
    (112, PC),
    (1, PC),
    (13, PC),
    (8, PC),
]


@pytest.mark.parametrize("look", builtin_looks(), ids=lambda look: look.id)
def test_a_zone_frame_renders_in_under_5_ms(look: Look) -> None:
    lights = [ZoneLight(f"light-{i}", count, caps) for i, (count, caps) in enumerate(HOME)]
    assert sum(light.led_count for light in lights) == 412
    runtime = ZoneRuntime("home", look, lights, clock=BeatClock(), latency_s=lambda _: 0.05)
    durations = []
    for step in range(240):
        started = time.perf_counter()
        runtime.tick(1000.0 + step / 60)
        durations.append(time.perf_counter() - started)
    assert statistics.median(durations) < 0.005
