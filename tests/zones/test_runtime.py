from __future__ import annotations

import itertools
from collections.abc import Iterator, Sequence
from typing import Any, ClassVar

import numpy as np
import pytest
from loguru import logger

from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.effects.context import RenderContext
from dj_ledfx.effects.field import FieldEffect
from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.looks.model import Layer, Look
from dj_ledfx.types import FloatRGB
from dj_ledfx.zones.runtime import ZoneLight, ZoneRuntime

TILE = DeviceCapabilities(protocol="LIFX", matrix=True)
BULB = DeviceCapabilities(protocol="LIFX")
LAMP = DeviceCapabilities(protocol="Govee")
LIGHTS = (ZoneLight("tile", 4, TILE), ZoneLight("bulb", 1, BULB), ZoneLight("lamp", 3, LAMP))


class FlatField(FieldEffect):
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
def _reset_flat_field() -> Iterator[None]:
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
    latencies: dict[str, float] | None = None,
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
    assert runtime.generation == generation + 1  # firmware lights get the new settings
    runtime.update_look(_look(_glow(level=0.9)))
    assert runtime.field_effect is None and runtime.generation == generation + 2


def test_brightness_resends_firmware_only_when_lights_run_it() -> None:
    streamed = _runtime(_look(_field()))
    generation = streamed.generation
    streamed.set_brightness(0.3)
    assert streamed.brightness == 0.3 and streamed.generation == generation
    firmware = _runtime(_look(_field(), _glow()))
    generation = firmware.generation
    firmware.set_brightness(0.3)
    assert firmware.generation == generation + 1
