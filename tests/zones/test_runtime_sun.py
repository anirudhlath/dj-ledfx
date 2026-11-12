"""M6 rulings 4 and 5: every frame carries the sun the zone's env gives, and a look that
needs the sun waits dark without one, starting at the first tick that has one."""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np
import pytest
from runtime_fakes import FADE, glow_layer, latest, look_of, runtime_of
from sun_fakes import AT_DUSK, FixedSun

from dj_ledfx.effects.base import Effect
from dj_ledfx.effects.context import SUN_AZIMUTH, SUN_ELEVATION, RenderContext
from dj_ledfx.effects.field import FieldEffect
from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.looks.model import Layer
from dj_ledfx.types import FloatRGB
from dj_ledfx.zones.runtime import ZoneRuntime


class KeptContext(FieldEffect, register=False):
    """Flat white, keeping the moment it last drew (`last`)."""

    last: ClassVar[RenderContext | None] = None

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {}

    def get_params(self) -> dict[str, Any]:
        return {}

    def _apply_params(self, **kwargs: Any) -> None:
        pass

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        KeptContext.last = ctx
        return np.ones((leds.count, 3), dtype=np.float32)


@pytest.fixture(autouse=True)
def _kept_context() -> None:
    Effect._registry["kept_context"] = KeptContext  # conftest drops it after the test
    KeptContext.last = None


KEPT = Layer(id="kept", name="Kept", type="field", kind="kept_context")
NEEDS_SUN = look_of(KEPT, needs=("sun",))


def _ticked(runtime: ZoneRuntime, *steps: int) -> ZoneRuntime:
    for step in steps:
        runtime.tick(100.0 + step / 60)
    return runtime


def test_a_look_that_needs_the_sun_waits_dark_without_one() -> None:
    runtime = _ticked(runtime_of(NEEDS_SUN, sun=lambda: None), 0, 1, 2)

    assert runtime.waiting_for == ("sun",)
    assert runtime.state == "waiting"
    assert not latest(runtime).any()
    assert KeptContext.last is None  # nothing drawn while it waits


def test_a_sun_arriving_starts_a_waiting_zone_and_says_so() -> None:
    sun = FixedSun(None)
    changes: list[str] = []
    runtime = _ticked(
        runtime_of(NEEDS_SUN, sun=sun, on_state_change=lambda rt: changes.append(rt.state)), 0
    )
    assert (runtime.state, changes) == ("waiting", [])

    sun.point = AT_DUSK
    _ticked(runtime, 1)

    assert (runtime.waiting_for, runtime.state) == ((), "running")
    assert latest(runtime).all()  # it draws from that tick's frame
    _ticked(runtime, 2, 3)
    assert changes == ["running"]  # once for the change

    sun.point = None
    _ticked(runtime, 4, 5)

    assert (runtime.waiting_for, runtime.state) == (("sun",), "waiting")
    assert changes == ["running", "waiting"]
    assert not latest(runtime).any()


# Scan 2: a waiting look claims no light for its firmware layers, so the tick that sees the
# sun arrive plans them again (the zone manager then applies the lights: test_manager.py).
def test_a_sun_arriving_lets_the_firmware_layers_claim_their_lights() -> None:
    sun = FixedSun(None)
    runtime = _ticked(runtime_of(look_of(KEPT, glow_layer(), needs=("sun",)), sun=sun), 0)
    assert runtime.mode_of("tile") == "streaming"

    sun.point = AT_DUSK
    _ticked(runtime, 1)
    assert runtime.mode_of("tile") == "own-effect"
    route = runtime.route_for("tile")
    assert route is not None and not route.streaming

    sun.point = None
    _ticked(runtime, 2)
    assert runtime.mode_of("tile") == "streaming"


# The looks a transition replaces never tick, so the zone's tick follows the sun for them;
# a twin is its zone as it is, waiting while its zone still waits.
def test_the_looks_a_transition_replaces_follow_the_sun_with_it() -> None:
    sun = FixedSun(None)
    replaced = _ticked(runtime_of(NEEDS_SUN, sun=sun), 0)
    sun.point = AT_DUSK  # replaced hasn't ticked since
    twin = replaced.twin()
    assert twin.waiting_for == ("sun",)

    runtime = runtime_of(look_of(KEPT), sun=sun)
    runtime.begin_transition(FADE, [twin])
    _ticked(runtime, 1)

    assert runtime.transition_sources == (twin,)
    assert (twin.waiting_for, twin.state) == ((), "running")


def test_every_frame_carries_the_sun_the_env_gives() -> None:
    _ticked(runtime_of(look_of(KEPT), sun=lambda: AT_DUSK), 0)

    assert KeptContext.last is not None
    signals = KeptContext.last.signals
    assert (signals.get(SUN_ELEVATION), signals.get(SUN_AZIMUTH)) == (
        AT_DUSK.elevation_deg,
        AT_DUSK.azimuth_deg,
    )


def test_a_look_that_needs_nothing_never_waits_for_the_sun() -> None:
    changes: list[str] = []
    runtime = _ticked(
        runtime_of(look_of(KEPT), sun=lambda: None, on_state_change=lambda rt: changes.append("")),
        0,
        1,
    )

    assert (runtime.waiting_for, runtime.state, changes) == ((), "running", [])
    assert latest(runtime).all()
    assert KeptContext.last is not None
    assert KeptContext.last.signals.get(SUN_ELEVATION, -99.0) == -99.0  # no sun signal
