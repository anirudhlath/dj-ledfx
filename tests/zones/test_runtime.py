from __future__ import annotations

import itertools
from collections.abc import Iterator, Sequence
from types import MappingProxyType
from typing import Any, ClassVar

import numpy as np
import pytest
from loguru import logger

from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.effects.base import Effect
from dj_ledfx.effects.context import RenderContext, render_context
from dj_ledfx.effects.field import FieldEffect
from dj_ledfx.effects.firmware_lifx import LifxFlame
from dj_ledfx.effects.ledset import LedSet, PlacedLeds, Space
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.looks.model import Layer, Look
from dj_ledfx.types import FloatRGB, RenderedFrame
from dj_ledfx.zones.runtime import ZoneLight, ZoneRuntime

TILE = DeviceCapabilities(protocol="LIFX", matrix=True)
BULB = DeviceCapabilities(protocol="LIFX")
LAMP = DeviceCapabilities(protocol="Govee")
LIGHTS = (ZoneLight("tile", 4, TILE), ZoneLight("bulb", 1, BULB), ZoneLight("lamp", 3, LAMP))


class FlatField(FieldEffect, register=False):
    """Flat grey at `level`; raises or returns NaN when the test asks it to."""

    mode: ClassVar[str] = "ok"

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {"level": EffectParam(type="float", default=0.5, min=0.0, max=1.0)}

    def __init__(self, level: float = 0.5) -> None:
        self.level = level

    def get_params(self) -> dict[str, Any]:
        return {"level": self.level}

    def _apply_params(self, **kwargs: Any) -> None:
        self.level = float(kwargs.get("level", self.level))

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        if FlatField.mode == "raise":
            raise RuntimeError("boom")
        value = np.nan if FlatField.mode == "nan" else self.level
        return np.full((leds.count, 3), value, dtype=np.float32)


@pytest.fixture(autouse=True)
def _flat_field() -> Iterator[None]:
    Effect._registry["flat_field"] = FlatField  # conftest drops it after each test
    FlatField.mode = "ok"
    yield
    FlatField.mode = "ok"


def _field(level: float = 0.5, opacity: float = 1.0) -> Layer:
    return Layer(
        id="field",
        name="Flat",
        type="field",
        kind="flat_field",
        opacity=opacity,
        settings={"level": level},
    )


def _glow(level: float = 0.5) -> Layer:
    return Layer(
        id="glow", name="Glow", type="firmware", kind="glow_firmware", settings={"level": level}
    )


def _look(*layers: Layer, needs: tuple[Any, ...] = ()) -> Look:
    return Look(id="test", name="Test", category="ambient", layers=layers, needs=needs)


def _runtime(
    look: Look,
    lights: Sequence[ZoneLight] = LIGHTS,
    latencies: dict[str, float | None] | None = None,
    **kwargs: Any,
) -> ZoneRuntime:
    known = latencies or {}
    return ZoneRuntime(
        "zone",
        look,
        lights,
        clock=BeatClock(),
        latency_s=lambda device_id: known.get(device_id, 0.02),
        **kwargs,
    )


def _latest(runtime: ZoneRuntime) -> np.ndarray:
    frame = runtime.ring.find_nearest(1e9)
    assert frame is not None
    return frame.colors


def test_firmware_runs_where_supported_and_the_field_plays_elsewhere() -> None:
    runtime = _runtime(_look(_field(), _glow()))
    claim = runtime.claim_for("tile")
    assert claim is not None and claim[1].display_name == "Glow"
    assert runtime.mode_of("tile") == "own-effect"
    assert runtime.mode_of("bulb") == runtime.mode_of("lamp") == "streaming"
    tile, bulb = runtime.route_for("tile"), runtime.route_for("bulb")
    assert tile is not None and not tile.streaming
    assert bulb is not None and bulb.streaming and (bulb.start, bulb.stop) == (4, 5)


def test_a_firmware_only_look_streams_its_copy_to_lights_that_cannot_run_it() -> None:
    runtime = _runtime(_look(_glow(level=0.4)), brightness=0.5)
    assert runtime.mode_of("lamp") == "streamed-copy"
    assert runtime.effect_name("lamp") == "Glow"
    runtime.tick(100.0)
    assert np.allclose(_latest(runtime), 0.2)  # the copy everywhere, at half brightness


def test_the_top_firmware_layer_claims_first() -> None:
    flame = Layer(id="flame", name="Flame", type="firmware", kind="lifx_flame")
    runtime = _runtime(_look(_glow(), flame))
    claim = runtime.claim_for("tile")
    assert claim is not None and claim[1].display_name == "LIFX Flame"
    assert runtime.effect_name("lamp") == "LIFX Flame"  # the copy comes from the top layer


def test_a_rejected_firmware_effect_falls_back_to_its_streamed_copy() -> None:
    runtime = _runtime(_look(_field(), _glow()))
    runtime.mark_emulated("tile")
    assert runtime.claim_for("tile") is None
    assert runtime.mode_of("tile") == "streamed-copy"
    route = runtime.route_for("tile")
    assert route is not None and route.streaming


# E3: a layer's copy is drawn on its own lights only, as the whole zone would draw it.
def test_a_streamed_copy_is_drawn_as_on_the_whole_zone() -> None:
    flame = Layer(id="flame", name="Flame", type="firmware", kind="lifx_flame")
    lights = (ZoneLight("bulb", 1, BULB), ZoneLight("tile", 4, TILE), ZoneLight("lamp", 3, LAMP))
    runtime = _runtime(_look(_field(), flame), lights)
    runtime.mark_emulated("tile")
    runtime.tick(100.0)
    frame = runtime.ring.find_nearest(1e9)
    assert frame is not None
    ctx = render_context(BeatClock(), frame.target_time, 1 / 60)
    whole = LifxFlame().emulate(ctx, runtime.leds)
    assert np.array_equal(frame.colors[1:5], whole[1:5])
    assert np.allclose(frame.colors[[0, 5, 6, 7]], 0.5)  # the field on the others


# E11: the ring keeps every frame, so each tick renders a new array.
def test_each_tick_renders_a_new_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = _runtime(_look(_field()))
    written: list[RenderedFrame] = []
    monkeypatch.setattr(runtime.ring, "write", written.append)
    runtime.tick(100.0)
    runtime.tick(100.1)
    assert len(written) == 2
    assert not np.shares_memory(written[0].colors, written[1].colors)


def test_frames_are_rendered_for_now_plus_the_horizon() -> None:
    runtime = _runtime(_look(_field()), latencies={"lamp": 0.1})
    runtime.tick(100.0)
    frame = runtime.ring.find_nearest(100.0)
    assert frame is not None
    assert frame.target_time == pytest.approx(100.0 + 0.1 + 1 / 60)
    assert frame.colors.dtype == np.float32 and frame.colors.shape == (8, 3)


def test_the_horizon_is_capped_by_the_lookahead() -> None:
    runtime = _runtime(_look(_field()), latencies={"lamp": 5.0}, max_lookahead_s=1.0)
    assert runtime.horizon_s == 1.0


# B13: a light that runs its own effect gets no frames, and a light that isn't connected
# (None) gets none yet; neither sets how far ahead the zone renders.
def test_the_horizon_counts_only_connected_lights_that_stream() -> None:
    latencies: dict[str, float | None] = {"tile": 0.5, "bulb": None, "lamp": 0.1}
    runtime = _runtime(_look(_field(), _glow()), latencies=latencies)
    assert runtime.mode_of("tile") == "own-effect"
    assert runtime.horizon_s == pytest.approx(0.1 + 1 / 60)


def test_brightness_and_opacity_scale_the_frame() -> None:
    runtime = _runtime(_look(_field(level=0.8, opacity=0.5)), brightness=0.5)
    runtime.tick(100.0)
    assert np.allclose(_latest(runtime), 0.2)


def test_a_crash_holds_the_last_good_frame_and_is_logged_once() -> None:
    runtime = _runtime(_look(_field()))
    runtime.tick(100.0)
    errors: list[str] = []
    sink = logger.add(lambda message: errors.append(str(message)), level="ERROR")
    try:
        FlatField.mode = "raise"
        runtime.tick(100.1)
        runtime.tick(100.2)
        assert runtime.state == "crashed"
        assert runtime.crash is not None
        assert (runtime.crash.layer, runtime.crash.message) == ("Flat", "RuntimeError: boom")
        assert runtime.ring.count == 1  # the last good frame is still there
        runtime.restart()
        assert runtime.state == "running"
        runtime.tick(100.3)  # still raising: crashes again, without logging again
        assert runtime.state == "crashed"
    finally:
        logger.remove(sink)
    assert len(errors) == 1

    FlatField.mode = "ok"
    runtime.restart()
    runtime.tick(100.4)
    assert runtime.state == "running" and runtime.ring.count == 2


def test_nan_is_a_crash() -> None:
    runtime = _runtime(_look(_field()))
    FlatField.mode = "nan"
    runtime.tick(100.0)
    assert runtime.crash is not None and "NaN" in runtime.crash.message
    assert runtime.ring.count == 0


def test_a_look_that_cannot_be_built_is_crashed_from_the_start() -> None:
    runtime = _runtime(_look(Layer(id="x", name="Retired", type="field", kind="retired_effect")))
    assert runtime.state == "crashed"
    assert runtime.crash is not None and runtime.crash.layer == "Retired"
    runtime.tick(100.0)
    assert runtime.ring.count == 0


def test_a_slow_zone_drops_its_frame_rate_and_shows_slow_after_30_s() -> None:
    timer = itertools.count(0.0, 0.006).__next__  # every render "takes" 6 ms
    runtime = _runtime(_look(_field()), timer=timer)
    now = 100.0
    for _ in range(29 * 60):
        runtime.tick(now)
        now += 1 / 60
    assert runtime.fps_actual == pytest.approx(30, abs=1)
    assert runtime.state == "running"
    for _ in range(2 * 60):
        runtime.tick(now)
        now += 1 / 60
    assert runtime.state == "slow"
    assert runtime.slow_since is not None


# B21: the runtime says when its state changes by itself, so no one has to poll it.
def test_a_zone_reports_slow_and_crashed_as_they_happen() -> None:
    changes: list[str] = []
    timer = itertools.count(0.0, 0.006).__next__  # every render "takes" 6 ms
    runtime = _runtime(
        _look(_field()), timer=timer, on_state_change=lambda zone: changes.append(zone.state)
    )
    now = 100.0
    for _ in range(31 * 60):
        runtime.tick(now)
        now += 1 / 60
    assert changes == ["slow"]

    FlatField.mode = "raise"
    runtime.tick(now)
    runtime.tick(now + 0.1)
    assert changes == ["slow", "crashed"]


def test_a_waiting_look_renders_dark_and_claims_nothing() -> None:
    runtime = _runtime(_look(_field(), _glow(), needs=("music",)))
    assert runtime.state == "waiting"
    assert runtime.waiting_for == ("music",)
    assert runtime.claim_for("tile") is None
    runtime.tick(100.0)
    assert not _latest(runtime).any()


def test_new_lights_rebuild_the_led_set_and_start_a_fresh_ring() -> None:
    runtime = _runtime(_look(_field()))
    runtime.tick(100.0)
    old_ring = runtime.ring
    runtime.set_lights([ZoneLight("tile", 64, TILE), ZoneLight("lamp", 3, LAMP)])
    assert runtime.ring is not old_ring and runtime.ring.count == 0
    assert runtime.leds.count == 67
    assert runtime.route_for("bulb") is None
    route = runtime.route_for("lamp")
    assert route is not None and (route.start, route.stop) == (64, 67)


def test_update_look_keeps_the_effect_when_the_layers_match() -> None:
    runtime = _runtime(_look(_field(0.5), _glow(level=0.5)))
    effect = runtime.field_effect
    generation = runtime.generation
    runtime.update_look(_look(_field(0.7), _glow(level=0.5)))
    assert runtime.field_effect is effect
    assert effect is not None and effect.get_params() == {"level": 0.7}
    assert runtime.generation == generation  # the firmware layer didn't change
    runtime.update_look(_look(_field(0.7), _glow(level=0.9)))
    assert runtime.generation > generation  # firmware lights get the new settings
    generation = runtime.generation
    runtime.update_look(_look(_glow(level=0.9)))
    assert runtime.field_effect is None and runtime.generation > generation


def test_brightness_resends_firmware_only_when_lights_run_it() -> None:
    streamed = _runtime(_look(_field()))
    generation = streamed.generation
    streamed.set_brightness(0.3)
    assert streamed.brightness == 0.3 and streamed.generation == generation
    firmware = _runtime(_look(_field(), _glow()))
    generation = firmware.generation
    firmware.set_brightness(0.3)
    assert firmware.generation > generation


class ProbeField(FieldEffect, register=False):
    """Black everywhere; remembers the LED set it last drew on."""

    seen: ClassVar[LedSet | None] = None

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {}

    def get_params(self) -> dict[str, Any]:
        return {}

    def _apply_params(self, **kwargs: Any) -> None:
        pass

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        ProbeField.seen = leds
        return np.zeros((leds.count, 3), dtype=np.float32)


def test_a_runtime_draws_its_lights_where_the_map_puts_them() -> None:
    Effect._registry["probe_field"] = ProbeField
    sofa = np.array([6.0, 2.0, 0.5], dtype=np.float32)
    space = Space(anchors=MappingProxyType({"sofa": sofa}), rooms=("west", "east"), ceiling=3.0)
    lamp = PlacedLeds.from_positions(np.array([[1.0, 1.0, 0.2], [1.0, 1.0, 0.5], [1.0, 1.0, 0.8]]))
    lights = (ZoneLight("lamp", 3, LAMP, placed=lamp, room=0), ZoneLight("bulb", 1, BULB, room=1))
    look = _look(Layer(id="probe", name="Probe", type="field", kind="probe_field"))

    runtime = _runtime(look, lights, space=space)
    runtime.tick(100.0)

    seen = ProbeField.seen
    assert seen is not None and runtime.space is space
    assert np.allclose(seen.pos[:3], lamp.pos)
    assert np.allclose(seen.pos[3], lamp.pos.mean(axis=0))  # the unplaced bulb joins the lamp
    assert seen.room.tolist() == [0, 0, 0, 1]
    assert np.array_equal(seen.anchors["sofa"], sofa) and seen.space.ceiling == 3.0

    runtime.set_lights(lights[:1], Space(rooms=("west", "east"), ceiling=2.5))
    runtime.tick(101.0)

    seen = ProbeField.seen
    assert seen is not None and seen.count == 3
    assert seen.space.ceiling == 2.5 and dict(seen.anchors) == {}


def test_zone_lights_with_the_same_placement_are_equal() -> None:
    points = np.array([[1.0, 1.0, 0.2], [1.0, 1.0, 0.8]])
    one = ZoneLight("lamp", 2, LAMP, placed=PlacedLeds.from_positions(points))
    other = ZoneLight("lamp", 2, LAMP, placed=PlacedLeds.from_positions(points.copy()))
    assert one == other
    assert one != ZoneLight("lamp", 2, LAMP, placed=PlacedLeds.from_positions(points + 1.0))
