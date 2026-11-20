"""M6 rulings 4 and 5: every frame carries the sun the zone's env gives, and a look that
needs the sun waits dark without one, starting at the first tick that has one."""

from __future__ import annotations

import itertools
from typing import Any, ClassVar

import numpy as np
import pytest
from runtime_fakes import FADE, field_layer, glow_layer, latest, look_of, runtime_of
from sun_fakes import AT_DUSK, FixedSun

from dj_ledfx.effects.base import Effect
from dj_ledfx.effects.context import SUN_AZIMUTH, SUN_ELEVATION, RenderContext
from dj_ledfx.effects.field import FieldEffect
from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.looks.model import Layer
from dj_ledfx.types import FloatRGB
from dj_ledfx.zones.runtime import STREAMS, ZoneRuntime


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


def _moment(step: int) -> float:
    return 100.0 + step / 60  # a tick a frame, at 60 a second


def _ticked(runtime: ZoneRuntime, *steps: int) -> ZoneRuntime:
    for step in steps:
        runtime.tick(_moment(step))
    return runtime


def _midpoint_step(runtime: ZoneRuntime, first: int) -> int:
    """The tick that passes the midpoint of the transition the runtime first renders at
    step `first`: read before that tick. Its first frame shows that moment plus the horizon,
    the midpoint comes half the fade later, and tick switches once the moment it's given is
    past it."""
    midpoint = _moment(first) + runtime.horizon_s + FADE.duration_s / 2.0
    return next(step for step in itertools.count(first) if _moment(step) >= midpoint)


def _waking_zone(sun: FixedSun) -> ZoneRuntime:
    """Zone `left` fading a look that streams in over one that waits for the sun and, once
    it has it, runs the glow on the tile."""
    waits = runtime_of(look_of(KEPT, glow_layer(), needs=("sun",)), sun=sun, zone_id="left")
    left = runtime_of(look_of(KEPT), sun=sun, zone_id="left")
    left.begin_transition(FADE, [waits])
    return left


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


# Spec §5.3: a light that runs a firmware effect in either look follows the old look until
# the midpoint, then switches whole. A look that waited when its transition began claimed
# nothing, so the sun arriving before the midpoint holds the light it now claims: it keeps
# streaming the old look's rows, unmixed, until the midpoint hands it over.
@pytest.mark.usefixtures("_fields")
def test_a_sun_arriving_mid_transition_holds_the_light_it_claims_until_the_midpoint() -> None:
    sun = FixedSun(None)
    switched: list[ZoneRuntime] = []
    new_look = look_of(field_layer(level=0.0), glow_layer(), needs=("sun",))
    runtime = runtime_of(new_look, sun=sun, on_switch=switched.append)
    runtime.begin_transition(FADE, [runtime_of(look_of(KEPT), sun=sun)])  # white everywhere
    midpoint = _midpoint_step(runtime, 0)
    _ticked(runtime, 0)  # the transition starts at this frame
    tile, bulb = runtime.leds.slice_for("tile"), runtime.leds.slice_for("bulb")
    assert tile is not None and bulb is not None

    sun.point = AT_DUSK
    for step in range(1, 31):  # to about a quarter of the way
        _ticked(runtime, step)
        assert runtime.applied_key("tile") == STREAMS  # the old look's, as before the sun
    frame = latest(runtime)
    assert 0.0 < frame[bulb.start, 0] < 1.0  # a streamed light mixes
    assert (frame[tile.start : tile.stop] == 1.0).all()  # the held one shows the old look

    for step in range(31, midpoint):
        _ticked(runtime, step)
        assert (runtime.applied_key("tile"), switched) == (STREAMS, [])
    _ticked(runtime, midpoint)
    assert switched == [runtime]  # on the tick that passes the midpoint
    assert runtime.handing_over == frozenset({"tile"})
    assert (latest(runtime)[tile.start : tile.stop] == 1.0).all()  # the old look's till applied
    runtime.handed_over(["tile"])
    assert runtime.mode_of("tile") == "own-effect"
    assert runtime.applied_key("tile") != STREAMS
    _ticked(runtime, midpoint + 1)
    assert (latest(runtime)[tile.start : tile.stop] == 0.5).all()  # the new look's glow, whole


# The jump spec §5.3 asks for (_follow_inputs): the tile mixed with the bulb while the new
# look waited, and the frame after the sun let that look claim it shows the old look whole.
@pytest.mark.usefixtures("_fields")
def test_a_hold_added_mid_fade_jumps_the_light_back_to_the_old_look() -> None:
    sun = FixedSun(None)
    runtime = runtime_of(look_of(field_layer(level=0.0), glow_layer(), needs=("sun",)), sun=sun)
    runtime.begin_transition(FADE, [runtime_of(look_of(KEPT), sun=sun)])  # white everywhere
    _ticked(runtime, *range(48))  # about 0.4 of the way
    tile, bulb = runtime.leds.slice_for("tile"), runtime.leds.slice_for("bulb")
    assert tile is not None and bulb is not None
    before = latest(runtime)
    assert before[tile.start, 0] == before[bulb.start, 0] < 0.75  # both mix, over dark

    sun.point = AT_DUSK
    _ticked(runtime, 48)
    after = latest(runtime)
    assert (after[tile.start : tile.stop] == 1.0).all()  # the jump: the old look, whole
    assert after[bulb.start, 0] < before[bulb.start, 0]  # the bulb mixes on


# The other thing a hold added mid-way does (_follow_inputs): when the look that wakes is
# the one replaced, the tile runs that old look's effect until the midpoint, then goes over.
def test_a_replaced_look_that_wakes_mid_transition_runs_its_effect_until_the_midpoint() -> None:
    sun = FixedSun(None)
    switched: list[ZoneRuntime] = []
    old = runtime_of(look_of(KEPT, glow_layer(), needs=("sun",)), sun=sun)
    runtime = runtime_of(look_of(KEPT), sun=sun, on_switch=switched.append)
    runtime.begin_transition(FADE, [old])
    midpoint = _midpoint_step(runtime, 0)
    _ticked(runtime, 0)

    sun.point = AT_DUSK
    _ticked(runtime, 1)
    assert runtime.applied_key("tile") == old.applied_key("tile") != STREAMS
    assert runtime.mode_of("tile") == "own-effect"

    _ticked(runtime, *range(2, midpoint + 1))
    assert (switched, runtime.handing_over) == ([runtime], frozenset({"tile"}))
    assert runtime.applied_key("tile") == STREAMS  # the new look streams it, once applied


# Past the midpoint nothing is held: a light the sun lets the new look claim goes over at
# once, with nothing to hand over.
def test_a_sun_arriving_past_the_midpoint_holds_nothing() -> None:
    sun = FixedSun(None)
    switched: list[ZoneRuntime] = []
    new_look = look_of(KEPT, glow_layer(), needs=("sun",))
    runtime = runtime_of(new_look, sun=sun, on_switch=switched.append)
    runtime.begin_transition(FADE, [runtime_of(look_of(KEPT), sun=sun)])
    midpoint = _midpoint_step(runtime, 0)
    _ticked(runtime, *range(midpoint))

    sun.point = AT_DUSK
    _ticked(runtime, midpoint)  # the tick that passes the midpoint
    assert runtime.applied_key("tile") != STREAMS
    assert runtime.mode_of("tile") == "own-effect"
    assert (switched, runtime.handing_over) == ([], frozenset())  # it held nothing


# A start mid-transition takes the mix on (settle()): the transition it took on holds
# nothing more when the sun comes, and the newer one holds the light on that look instead.
@pytest.mark.usefixtures("_fields")
def test_a_transition_a_newer_start_took_on_holds_nothing_more() -> None:
    sun = FixedSun(None)
    waking = runtime_of(look_of(field_layer(level=0.0), glow_layer(), needs=("sun",)), sun=sun)
    waking.begin_transition(FADE, [runtime_of(look_of(KEPT), sun=sun)])  # white everywhere
    _ticked(waking, *range(10))
    newer = runtime_of(look_of(KEPT), sun=sun)
    newer.begin_transition(FADE, [waking])  # the same zone: waking's lights go over
    _ticked(newer, 10)

    sun.point = AT_DUSK
    _ticked(newer, 11)
    assert newer.applied_key("tile") == waking.applied_key("tile") != STREAMS
    tile = newer.leds.slice_for("tile")
    assert tile is not None
    rows = latest(newer)[tile.start : tile.stop]  # waking's, as newer holds the tile
    assert ((rows > 0.5) & (rows < 1.0)).all()  # its mix of white and its glow (0.5)


# twin() copies the lights its zone's transition holds: a hold the sun adds in the twin, as
# the zone that took it renders it, stays out of the zone the twin was made from.
def test_a_hold_added_in_a_twin_stays_out_of_its_zones_transition() -> None:
    sun = FixedSun(None)
    left = _waking_zone(sun)
    _ticked(left, 0, 1, 2)
    twin = left.twin()
    right = runtime_of(look_of(KEPT), sun=sun, zone_id="right")
    right.begin_transition(FADE, [twin])
    _ticked(right, 3)

    sun.point = AT_DUSK
    _ticked(right, 4)  # long before left's midpoint
    assert right.applied_key("tile") == twin.applied_key("tile") != STREAMS
    assert left.applied_key("tile") == STREAMS


# A twin never ticks or switches, but it holds as its zone would have: up to the tick its
# zone switched at, and not from that tick on, wherever the zone that took it is.
@pytest.mark.parametrize(("sun_at", "held"), [(-1, True), (0, False)])
def test_a_twin_holds_until_the_tick_its_zone_switched_at(sun_at: int, held: bool) -> None:
    sun, alone_sun = FixedSun(None), FixedSun(None)
    left, alone = _waking_zone(sun), _waking_zone(alone_sun)  # alone: left, left to tick
    midpoint = _midpoint_step(left, 0)
    _ticked(left, *range(30))
    twin = left.twin()
    right = runtime_of(look_of(KEPT), sun=sun, zone_id="right")
    right.begin_transition(FADE, [twin])  # right's own midpoint is half a second later
    sun_step = midpoint + sun_at
    _ticked(right, *range(30, sun_step))
    _ticked(alone, *range(sun_step))

    sun.point = alone_sun.point = AT_DUSK
    _ticked(right, sun_step)
    _ticked(alone, sun_step)
    assert (right.applied_key("tile") != STREAMS) == held
    assert (alone.applied_key("tile") != STREAMS) == held


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
