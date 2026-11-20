"""An overlay's amount and the slot routes and the frame feed read (zones/overlay.py)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from runtime_fakes import field_layer, look_of, runtime_of

from dj_ledfx.zones.overlay import OVERLAY_EDGE_S, OverlayRun, OverlaySlot
from dj_ledfx.zones.runtime import ZoneRuntime

pytestmark = pytest.mark.usefixtures("_fields")

WALL = datetime(2026, 9, 24, 19, 0, tzinfo=UTC)


def _run(runtime: ZoneRuntime, started_t: float = 100.0, ends_t: float = 110.0) -> OverlayRun:
    return OverlayRun(
        runtime.look,
        "api",
        runtime,
        started_t,
        ends_t,
        WALL,
        WALL + timedelta(seconds=ends_t - started_t),
    )


def test_an_overlays_amount_eases_in_and_out_over_its_edges() -> None:
    run = _run(runtime_of(look_of(field_layer())))
    edge = OVERLAY_EDGE_S

    assert run.amount(99.0) == 0.0 and run.amount(100.0) == 0.0
    assert run.amount(100.0 + edge) == 1.0 and run.amount(110.0 - edge) == 1.0
    assert run.amount(105.0) == 1.0
    assert run.amount(110.0) == 0.0 and run.amount(111.0) == 0.0
    rising = [run.amount(100.0 + edge * k / 10) for k in range(11)]
    falling = [run.amount(110.0 - edge + edge * k / 10) for k in range(11)]
    assert rising == sorted(rising) and len(set(rising)) == 11
    assert falling == sorted(falling, reverse=True) and len(set(falling)) == 11
    assert 0.0 < run.amount(100.0 + edge / 2) < 1.0


def test_an_overlay_shorter_than_its_edges_peaks_below_full() -> None:
    run = _run(runtime_of(look_of(field_layer())), 100.0, 100.0 + OVERLAY_EDGE_S)

    peak = max(run.amount(100.0 + OVERLAY_EDGE_S * k / 100) for k in range(101))

    assert 0.0 < peak < 1.0
    assert run.amount(100.0 + OVERLAY_EDGE_S / 2) == pytest.approx(peak)  # the two edges meet


def test_the_slot_gives_nothing_for_a_light_it_doesnt_cover_or_of_another_led_count() -> None:
    runtime = runtime_of(look_of(field_layer(0.4)))  # tile 4 LEDs, bulb 1, lamp 3
    runtime.tick(105.0)
    slot = OverlaySlot(reaches=lambda d: d != "bulb")
    assert slot.over_at("lamp", 105.0, 3) is None  # nothing plays

    slot.run = _run(runtime)

    assert slot.over_at("lamp", 105.0, 3) is not None
    assert slot.over_at("elsewhere", 105.0, 3) is None  # not in the overlay
    assert slot.over_at("lamp", 105.0, 4) is None  # another LED count
    assert slot.over_at("bulb", 105.0, 1) is None  # its reaches says no
    assert slot.over_at("lamp", 110.0, 3) is None  # its amount is 0
    empty = _run(runtime_of(look_of(field_layer())))  # never ticked: its ring is empty
    slot.run = empty
    assert slot.over_at("lamp", 105.0, 3) is None


def test_the_slot_gives_the_overlays_colours_and_amount_at_a_moment() -> None:
    runtime = runtime_of(look_of(field_layer(0.4)))
    runtime.tick(105.0)
    slot = OverlaySlot(reaches=lambda d: True)
    slot.run = _run(runtime)

    full = slot.over_at("lamp", 105.0, 3)
    easing = slot.over_at("lamp", 100.0 + OVERLAY_EDGE_S / 2, 3)

    assert full is not None and full[1] == 1.0
    assert full[0].shape == (3, 3) and np.allclose(full[0], 0.4)
    assert easing is not None and easing[1] == pytest.approx(0.5)
