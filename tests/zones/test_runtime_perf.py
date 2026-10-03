"""Spec §9: each zone renders in under 5 ms on this home's LEDs. Run with -m perf."""

from __future__ import annotations

import statistics
import time
from dataclasses import replace
from typing import Any

import pytest
from map_home import seeded_space, seeded_zone_lights

from dj_ledfx.home.seed import handoff_home_json
from dj_ledfx.looks.builtin import builtin_looks
from dj_ledfx.looks.model import HeightMask, Look, LookModifiers, Mirror, Transform
from dj_ledfx.tempo.clock import TempoClock
from dj_ledfx.zones.runtime import FRAME_BUDGET_S, ZoneRuntime

pytestmark = pytest.mark.perf

EVERY_LOOK_MODIFIER = LookModifiers(
    trails_s=1.0, downbeat_flash=True, brightness_cap=0.8, evening=True
)


def with_every_modifier(look: Look) -> Look:
    """The look with every look modifier on, and a mask, a mirror and a transform on each
    streamed layer (a firmware layer takes none)."""
    layers = tuple(
        layer
        if layer.type == "firmware"
        else replace(
            layer,
            mask=HeightMask(0.3, 2.0),
            mirror=Mirror("x"),
            transform=Transform(offset=(0.5, 0.0, 0.0), rotate_deg=30.0, scale=1.5),
        )
        for layer in look.layers
    )
    return replace(look, layers=layers, modifiers=EVERY_LOOK_MODIFIER)


def home_runtime(look: Look, **kwargs: Any) -> ZoneRuntime:
    """The look on every seeded LED of this home, as the whole-home zone runs it."""
    lights = seeded_zone_lights()
    assert sum(light.led_count for light in lights) == handoff_home_json()["totals"]["leds"]
    return ZoneRuntime(
        "home",
        look,
        lights,
        clock=TempoClock(),
        latency_s=lambda _: 0.05,
        space=seeded_space(),
        **kwargs,
    )


def tick_times(runtime: ZoneRuntime, ticks: int = 240, start: float = 1000.0) -> list[float]:
    """How long each of `ticks` ticks took, 60 a second from `start`."""
    durations = []
    for step in range(ticks):
        started = time.perf_counter()
        runtime.tick(start + step / 60)
        durations.append(time.perf_counter() - started)
    return durations


@pytest.mark.parametrize("look", builtin_looks(), ids=lambda look: look.id)
def test_a_zone_frame_renders_in_under_5_ms(look: Look) -> None:
    runtime = home_runtime(look)

    assert statistics.median(tick_times(runtime)) < FRAME_BUDGET_S


# Spec §5.3: the modifiers run inside the same budget.
@pytest.mark.parametrize("look", builtin_looks(), ids=lambda look: look.id)
def test_a_zone_frame_with_every_modifier_renders_in_under_5_ms(look: Look) -> None:
    runtime = home_runtime(with_every_modifier(look), evening=lambda: 0.5)

    assert statistics.median(tick_times(runtime)) < FRAME_BUDGET_S
    assert runtime.fps_actual >= 59  # it never dropped to a lower frame rate
