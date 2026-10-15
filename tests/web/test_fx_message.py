"""The `fx` channel's message (web spec §12.4, "The `fx` payload")."""

from __future__ import annotations

import json
import time

import numpy as np
import pytest

from dj_ledfx.effects.fx import Fx, Rings, planes, rings
from dj_ledfx.effects.particle_tools import swarm
from dj_ledfx.web.fx import MAX_FX_PARTICLES, fx_message
from dj_ledfx.zones.frames import Stream, ZoneFx


def _shown(fx: Fx, brightness: float = 1.0, stream: Stream = "live") -> ZoneFx:
    return ZoneFx(stream, "z", fx, brightness)


def _both_forms() -> Rings:
    sphere = rings([0.0, 1.0, 1.0], 1.5, 0.3, (1.0, 0.0, 0.0))
    circle = rings([3.0, 3.0, 0.0], 2.0, 0.3, (1.0, 0.0, 0.0), circle=True)
    return Rings(
        *(
            np.concatenate([getattr(sphere, name), getattr(circle, name)])
            for name in ("centre", "radius", "width", "colour", "circle")
        )
    )


def test_each_kind_is_sent_as_the_payload_names_it() -> None:
    fx = Fx(
        particles=swarm([[1.0, 2.0, 0.5]], (1.0, 0.5, 0.25), 0.2),
        rings=_both_forms(),
        planes=planes(
            [[1.0, 1.0, 1.0], [2.0, 2.0, 2.0]],
            [[0.0, 0.0, 1.0], [0.0, 1.0, 0.0]],
            0.4,
            (0.0, 0.0, 1.0),
            ray=[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
        ),
    )

    message = fx_message([_shown(fx), _shown(fx, stream="preview")])

    assert message["channel"] == "fx"
    live, preview = message["zones"]
    assert (live["zoneId"], live["stream"], preview["stream"]) == ("z", "live", "preview")
    assert live["particles"] == [[1.0, 2.0, 0.5, 1.0, 0.5, 0.25, 0.2]]  # x y z r g b size
    red = [1.0, 0.0, 0.0]
    assert live["rings"] == [
        {"center": [0.0, 1.0, 1.0], "radius": 1.5, "width": 0.3, "rgb": red, "form": "sphere"},
        {"center": [3.0, 3.0, 0.0], "radius": 2.0, "width": 0.3, "rgb": red, "form": "circle"},
    ]
    # A whole plane has no ray; a beam's ray says which half of it is lit.
    blue = [0.0, 0.0, 1.0]
    assert live["planes"] == [
        {"point": [1.0, 1.0, 1.0], "normal": [0.0, 0.0, 1.0], "width": 0.4, "rgb": blue},
        {
            "point": [2.0, 2.0, 2.0],
            "normal": [0.0, 1.0, 0.0],
            "width": 0.4,
            "rgb": blue,
            "ray": [1.0, 0.0, 0.0],
        },
    ]
    json.dumps(message, allow_nan=False)  # plain JSON


def test_colours_carry_the_zones_brightness_clipped_and_numbers_round_to_3_places() -> None:
    fx = Fx(particles=swarm([[1.23456, 0.0, 1.0]], (0.8, 1.6, 0.123456), 0.15))
    [zone] = fx_message([_shown(fx, brightness=0.5)])["zones"]
    assert zone["particles"] == [[1.235, 0.0, 1.0, 0.4, 0.8, 0.062, 0.15]]
    [zone] = fx_message([_shown(fx, brightness=1.0)])["zones"]
    assert zone["particles"][0][3:6] == [0.8, 1.0, 0.123]  # 1.6 clipped to 1


def test_what_rounds_to_black_or_holds_a_nan_is_left_out_and_so_is_an_empty_zone() -> None:
    fx = Fx(
        particles=swarm(
            [[0.0, 0.0, 1.0], [1.0, 0.0, 1.0], [np.nan, 0.0, 1.0]],
            [[1.0, 1.0, 1.0], [0.0004, 0.0, 0.0], [1.0, 1.0, 1.0]],
            0.2,
        ),
        rings=rings([0.0, 0.0, 0.0], np.inf, 0.1, (1.0, 1.0, 1.0)),
        planes=planes([0.0, 0.0, 1.0], (0.0, 0.0, 1.0), 0.2, (0.0, 0.0, 0.0)),
    )
    [zone] = fx_message([_shown(fx)])["zones"]
    assert zone["particles"] == [[0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 0.2]]
    assert "rings" not in zone and "planes" not in zone  # a kind with nothing is left out

    dark = _shown(fx, brightness=0.0)
    assert fx_message([dark]) == {"channel": "fx", "zones": []}
    assert fx_message([]) == {"channel": "fx", "zones": []}


def test_a_zone_sends_its_newest_particles_up_to_the_cap() -> None:
    count = MAX_FX_PARTICLES + 20
    places = [[i / 100.0, 0.0, 1.0] for i in range(count)]  # oldest first
    [zone] = fx_message([_shown(Fx(particles=swarm(places, (1.0, 1.0, 1.0), 0.1)))])["zones"]
    assert len(zone["particles"]) == MAX_FX_PARTICLES
    assert zone["particles"][0][0] == pytest.approx(0.2)  # the 20 oldest are cut
    assert zone["particles"][-1][0] == pytest.approx((count - 1) / 100.0)


@pytest.mark.perf
def test_two_full_zones_encode_well_inside_a_frame() -> None:
    rng = np.random.default_rng(1)
    full = Fx(
        particles=swarm(
            rng.uniform(0.0, 8.0, (MAX_FX_PARTICLES, 3)),
            rng.uniform(0.0, 1.0, (MAX_FX_PARTICLES, 3)),
            0.2,
        ),
        rings=rings(rng.uniform(0.0, 8.0, (8, 3)), 2.0, 0.3, (1.0, 0.5, 0.0)),
        planes=planes(rng.uniform(0.0, 8.0, (2, 3)), (0.0, 0.0, 1.0), 0.2, (0.0, 1.0, 1.0)),
    )
    shown = [_shown(full), _shown(full, stream="preview")]
    durations = []
    for _ in range(50):
        started = time.perf_counter()
        json.dumps(fx_message(shown))
        durations.append(time.perf_counter() - started)
    assert sorted(durations)[25] < 0.0025  # half a frame's budget, for every session at once
