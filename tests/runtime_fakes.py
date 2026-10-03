"""Fakes for zone runtime tests: three lights, field effects that are easy to read, and
looks and runtimes made of them. A test file registers the fields with an autouse fixture
that calls register_fields() (conftest drops them after each test)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import fields
from typing import Any, ClassVar

import numpy as np
from conftest import nearest_frame

from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.effects.base import Effect
from dj_ledfx.effects.context import RenderContext
from dj_ledfx.effects.field import FieldEffect
from dj_ledfx.effects.ledset import NO_ROOM, LedSet, PlacedLeds
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.looks.model import Layer, Look
from dj_ledfx.tempo.clock import TempoClock
from dj_ledfx.types import FloatRGB
from dj_ledfx.zones.runtime import RuntimeEnv, ZoneLight, ZoneRuntime

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


class PlaceField(FieldEffect, register=False):
    """Each LED's colour is the position the effect sees it at, x, y and z in metres: a
    layer's mirror and transform show in the frame as moved positions. `seen` keeps every
    LED set it rendered, in order."""

    seen: ClassVar[list[LedSet]] = []

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {}

    def get_params(self) -> dict[str, Any]:
        return {}

    def _apply_params(self, **kwargs: Any) -> None:
        pass

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        PlaceField.seen.append(leds)
        return np.array(leds.pos, dtype=np.float32)


def register_fields() -> None:
    Effect._registry["flat_field"] = FlatField
    Effect._registry["place_field"] = PlaceField
    FlatField.mode = "ok"
    PlaceField.seen = []


def field_layer(level: float = 0.5, opacity: float = 1.0, **changes: Any) -> Layer:
    """A flat field layer; changes set any other field of the Layer (a mask, a blend)."""
    return Layer(
        id=changes.pop("id", "field"),
        name=changes.pop("name", "Flat"),
        type="field",
        kind="flat_field",
        opacity=opacity,
        settings={"level": level},
        **changes,
    )


def place_layer(**changes: Any) -> Layer:
    return Layer(id="place", name="Place", type="field", kind="place_field", **changes)


def glow_layer(level: float = 0.5) -> Layer:
    return Layer(
        id="glow", name="Glow", type="firmware", kind="glow_firmware", settings={"level": level}
    )


def look_of(*layers: Layer, needs: tuple[Any, ...] = (), **changes: Any) -> Look:
    return Look(
        id=changes.pop("id", "test"),
        name=changes.pop("name", "Test"),
        category="ambient",
        layers=layers,
        needs=needs,
        **changes,
    )


def placed_light(
    device_id: str,
    *points: tuple[float, float, float],
    caps: DeviceCapabilities = LAMP,
    room: int = NO_ROOM,
) -> ZoneLight:
    """A light whose LEDs the map puts at these points."""
    placed = PlacedLeds.from_positions(np.array(points, dtype=np.float64))
    return ZoneLight(device_id, len(points), caps, placed=placed, room=room)


ENV_FIELDS = frozenset(f.name for f in fields(RuntimeEnv))


def runtime_of(
    look: Look,
    lights: Sequence[ZoneLight] = LIGHTS,
    latencies: dict[str, float | None] | None = None,
    clock: TempoClock | None = None,
    **kwargs: Any,
) -> ZoneRuntime:
    """The look on these lights, 20 ms away unless `latencies` says otherwise. Keyword
    arguments set the RuntimeEnv's fields (timer, watched, evening...) or the runtime's."""
    known = latencies or {}
    env = RuntimeEnv(
        clock=clock or TempoClock(),
        latency_s=lambda device_id: known.get(device_id, 0.02),
        **{name: kwargs.pop(name) for name in ENV_FIELDS & kwargs.keys()},
    )
    return ZoneRuntime(kwargs.pop("zone_id", "zone"), look, lights, env, **kwargs)


def latest(runtime: ZoneRuntime) -> np.ndarray:
    """The newest frame the runtime rendered."""
    return nearest_frame(runtime.ring, 1e9).colors


def sent(runtime: ZoneRuntime, light: str, at: float, leds: int) -> np.ndarray:
    """What a light's route sends at `at`, to a device of `leds` LEDs."""
    route = runtime.route_for(light)
    assert route is not None
    colors = route.colors_at(at, leds)
    assert colors is not None
    return colors
