"""Spec §9: each zone renders in under 5 ms on this home's LEDs. Run with -m perf."""

from __future__ import annotations

import itertools
import statistics
import time
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest
from conftest import builtin_look
from map_home import seeded_space, seeded_zone_lights

from dj_ledfx.home.model import Location
from dj_ledfx.home.seed import handoff_home_json
from dj_ledfx.home.sun import Evening, evening_amount
from dj_ledfx.looks.builtin import builtin_looks
from dj_ledfx.looks.model import (
    MAX_TRANSITION_S,
    HeightMask,
    Look,
    LookModifiers,
    Mirror,
    Transform,
    Transition,
    TransitionKind,
)
from dj_ledfx.tempo.clock import TempoClock
from dj_ledfx.zones.runtime import FRAME_BUDGET_S, RuntimeEnv, ZoneLight, ZoneRuntime

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


def home_runtime(look: Look, **env: Any) -> ZoneRuntime:
    """The look on every seeded LED of this home, as the whole-home zone runs it; `env`
    sets RuntimeEnv's fields."""
    lights = seeded_zone_lights()
    assert sum(light.led_count for light in lights) == handoff_home_json()["totals"]["leds"]
    return zone_runtime("home", look, lights, **env)


def zone_runtime(zone_id: str, look: Look, lights: Sequence[ZoneLight], **env: Any) -> ZoneRuntime:
    """The look on these seeded lights, as a zone of them runs it."""
    return ZoneRuntime(
        zone_id,
        look,
        lights,
        RuntimeEnv(TempoClock(), lambda _: 0.05, **env),
        space=seeded_space(),
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


# Spec §5.3: the evening is worked out once a second, inside whichever zone's tick asks
# first. A real Evening at a made-up place, a sixtieth of a second on at each tick, so the
# ticks that work it out again (every 60th) are measured too.
def test_a_zone_frame_that_works_the_evening_out_renders_in_under_5_ms() -> None:
    place, at = Location("Test", 12.5, -40.25), datetime(2026, 3, 9, 20, 15, tzinfo=UTC)
    assert 0.0 < evening_amount(place.lat, place.lon, at) < 1.0  # it warms the frame
    ticks = itertools.count()
    evening = Evening(lambda: place, now=lambda: at, clock=lambda: next(ticks) / 60)
    runtime = home_runtime(with_every_modifier(builtin_look("aurora")), evening=evening)

    durations = tick_times(runtime)

    assert statistics.median(durations) < FRAME_BUDGET_S
    assert statistics.median(durations[60::60]) < FRAME_BUDGET_S  # worked out again


def _heavy(look_id: str) -> ZoneRuntime:
    """One of the heaviest looks, every modifier on, on every LED of this home."""
    look = next(look for look in builtin_looks() if look.id == look_id)
    return home_runtime(with_every_modifier(look), evening=lambda: 0.5)


# Spec §5.3: during a transition the zone renders both looks, and both count against the
# budget. The two heaviest looks with every modifier, 4 s into the longest transition.
@pytest.mark.parametrize("kind", ["fade", "wipe", "spread", "dissolve"])
def test_a_zone_frame_mid_transition_renders_in_under_5_ms(kind: TransitionKind) -> None:
    old, new = _heavy("aurora"), _heavy("lava")
    new.begin_transition(Transition(kind=kind, duration_s=MAX_TRANSITION_S), [old])

    durations = tick_times(new)

    assert new.state == "transition"
    assert statistics.median(durations) < FRAME_BUDGET_S
    assert new.fps_actual >= 59  # it never dropped to a lower frame rate


# The most a zone renders at once: a start while its transition plays mixes three looks.
def test_three_looks_mid_transition_render_in_under_5_ms() -> None:
    first, second, third = _heavy("aurora"), _heavy("lava"), _heavy("focus")
    second.begin_transition(Transition(kind="dissolve", duration_s=MAX_TRANSITION_S), [first])
    third.begin_transition(Transition(kind="spread", duration_s=MAX_TRANSITION_S), [second])

    durations = tick_times(third)

    assert third.state == "transition" and second.state == "transition"
    assert statistics.median(durations) < FRAME_BUDGET_S
    assert third.fps_actual >= 59


# Ruling 13: a zone's own chain is at most three looks, and each zone a start takes lights
# from adds its twin, so what a start renders is bounded by the number of zones. The whole
# home, mid-transition from its own two looks, takes its lights back from two zones that
# are mid-transition too: seven looks in one frame.
def test_a_start_taking_lights_from_two_zones_mid_transition_renders_in_under_5_ms() -> None:
    lights = seeded_zone_lights()
    third = len(lights) // 3
    parts = {
        "home": lights[:third],
        "west": lights[third : 2 * third],
        "east": lights[2 * third :],
    }
    longest = Transition(kind="dissolve", duration_s=MAX_TRANSITION_S)
    latest: dict[str, ZoneRuntime] = {}
    for zone_id, part in parts.items():
        first, second = (
            zone_runtime(
                zone_id, with_every_modifier(builtin_look(look_id)), part, evening=lambda: 0.5
            )
            for look_id in ("aurora", "lava")
        )
        second.begin_transition(longest, [first])
        latest[zone_id] = second
    new = home_runtime(with_every_modifier(builtin_look("focus")), evening=lambda: 0.5)
    new.begin_transition(
        Transition(kind="spread", duration_s=MAX_TRANSITION_S),
        [latest["home"], latest["west"].twin(), latest["east"].twin()],
    )

    durations = tick_times(new)

    assert len(new.transition_sources) == 3 and new.state == "transition"
    assert all(len(source.transition_sources) == 1 for source in new.transition_sources)
    assert statistics.median(durations) < FRAME_BUDGET_S
    assert new.fps_actual >= 59
