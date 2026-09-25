"""Spec §9: each zone renders in under 5 ms on this home's LEDs. Run with -m perf."""

from __future__ import annotations

import statistics
import time

import pytest
from map_home import seeded_space, seeded_zone_lights

from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.home.seed import handoff_home_json
from dj_ledfx.looks.builtin import builtin_looks
from dj_ledfx.looks.model import Look
from dj_ledfx.zones.runtime import ZoneRuntime

pytestmark = pytest.mark.perf


@pytest.mark.parametrize("look", builtin_looks(), ids=lambda look: look.id)
def test_a_zone_frame_renders_in_under_5_ms(look: Look) -> None:
    lights = seeded_zone_lights()
    assert sum(light.led_count for light in lights) == handoff_home_json()["totals"]["leds"]
    runtime = ZoneRuntime(
        "home",
        look,
        lights,
        clock=BeatClock(),
        latency_s=lambda _: 0.05,
        space=seeded_space(),
    )
    durations = []
    for step in range(240):
        started = time.perf_counter()
        runtime.tick(1000.0 + step / 60)
        durations.append(time.perf_counter() - started)
    assert statistics.median(durations) < 0.005
