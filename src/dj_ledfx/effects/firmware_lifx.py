"""LIFX firmware effects: Flame and Morph (tile effects), Move (multizone effect) and
waveforms (spec §6.3). Each also renders a streamed copy for lights that can't run it."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, ClassVar

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.devices.lifx.base import LifxAdapterBase
from dj_ledfx.devices.lifx.packet import (
    HSBK,
    MultiZoneEffectType,
    TileEffectType,
    Waveform,
    rgb_to_hsbk,
)
from dj_ledfx.devices.lifx.strip import LifxStripAdapter
from dj_ledfx.devices.lifx.tile_chain import LifxTileChainAdapter
from dj_ledfx.effects.color import hex_to_rgb, palette_lerp, rgb_to_hex, to_float_rgb
from dj_ledfx.effects.firmware import FirmwareEffect, Params, require_adapter
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.types import RGB, clamp01

if TYPE_CHECKING:
    from dj_ledfx.devices.adapter import DeviceAdapter
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

FLAME_BASE = "#ff8a2a"
FLAME_COPY: list[RGB] = [(40, 4, 0), (190, 40, 0), (255, 120, 10), (255, 205, 110)]
MORPH_PALETTE = ["#ff3d6e", "#7b2cff", "#00b7ff", "#00e39a"]
MOVE_PALETTE = ["#ff0055", "#ffb300", "#00e5ff", "#8a2bff"]
WAVEFORMS = {
    "sine": Waveform.SINE,
    "triangle": Waveform.TRIANGLE,
    "saw": Waveform.SAW,
    "half_sine": Waveform.HALF_SINE,
    "pulse": Waveform.PULSE,
}
WAVEFORM_CYCLES = 1_000_000.0  # runs for weeks; a new look or Off interrupts it


def _period_ms(params: Params, default: float) -> int:
    return max(1, round(float(params.get("period", default)) * 1000))


def _hsbk(colour: str | RGB, brightness: float, kelvin: int = 3500) -> HSBK:
    r, g, b = hex_to_rgb(colour) if isinstance(colour, str) else colour
    hue, sat, bri, k = rgb_to_hsbk(r, g, b, kelvin=kelvin)
    return hue, sat, round(bri * clamp01(brightness)), k


def _loop(palette: list[RGB], positions: NDArray[np.float64]) -> NDArray[np.uint8]:
    """Palette colours around a loop: position 0 and 1 are the same colour."""
    return palette_lerp([*palette, palette[0]], np.mod(positions, 1.0))


def _cyclic(palette: list[RGB], positions: NDArray[np.float64]) -> FloatRGB:
    return to_float_rgb(_loop(palette, positions))


def _lifx(adapter: DeviceAdapter) -> LifxAdapterBase:
    # isinstance is all require_adapter does with the class, so an abstract one is fine
    return require_adapter(adapter, LifxAdapterBase, "a LIFX light")  # type: ignore[type-abstract]


def _matrix(adapter: DeviceAdapter) -> LifxTileChainAdapter:
    return require_adapter(adapter, LifxTileChainAdapter, "a LIFX matrix light")


def _multizone(adapter: DeviceAdapter) -> LifxStripAdapter:
    return require_adapter(adapter, LifxStripAdapter, "a LIFX multizone light")


def _palette_param(default: list[str]) -> EffectParam:
    return EffectParam(type="color_list", default=list(default), label="Palette")


class _TileFirmware(FirmwareEffect):
    """A matrix light's own tile effect: Flame or Morph."""

    tile_type: ClassVar[TileEffectType]

    def supports(self, caps: DeviceCapabilities) -> bool:
        return caps.protocol == "LIFX" and caps.matrix

    async def stop(self, adapter: DeviceAdapter) -> None:
        await _matrix(adapter).start_tile_effect(TileEffectType.OFF, 0)

    async def is_running(self, adapter: DeviceAdapter) -> bool | None:
        state = await _matrix(adapter).tile_effect()
        return None if state is None else state.effect == self.tile_type


class LifxFlame(_TileFirmware):
    display_name = "LIFX Flame"
    tile_type = TileEffectType.FLAME

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "period": EffectParam(
                type="float", default=5.0, min=1.0, max=20.0, step=0.5, label="Speed"
            )
        }

    def __init__(self, period: float = 5.0) -> None:
        self._period = period

    def get_params(self) -> dict[str, Any]:
        return {"period": self._period}

    def _apply_params(self, **kwargs: Any) -> None:
        if "period" in kwargs:
            self._period = float(kwargs["period"])

    async def start(self, adapter: DeviceAdapter, params: Params) -> None:
        matrix = _matrix(adapter)
        # The flame's intensity follows the light's own brightness.
        await matrix.set_colour(_hsbk(FLAME_BASE, float(params.get("brightness", 1.0))))
        await matrix.start_tile_effect(TileEffectType.FLAME, _period_ms(params, self._period))

    def emulate(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        phase = 2.0 * math.pi * ctx.t / self._period
        u = leds.local_u.astype(np.float64)
        height = leds.local[:, 2].astype(np.float64)
        wobble = (
            0.5
            + 0.25 * np.sin(phase * 3.1 + u * 11.0)
            + 0.25 * np.sin(phase * 5.3 + u * 23.0 + leds.device * 1.7)
        )
        heat = np.clip((1.0 - height) * 0.7 + wobble * 0.4 - 0.05, 0.0, 1.0)
        return to_float_rgb(palette_lerp(FLAME_COPY, heat))


class LifxMorph(_TileFirmware):
    display_name = "LIFX Morph"
    tile_type = TileEffectType.MORPH

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "period": EffectParam(
                type="float", default=6.0, min=1.0, max=20.0, step=0.5, label="Speed"
            ),
            "palette": _palette_param(MORPH_PALETTE),
        }

    def __init__(self, period: float = 6.0, palette: list[str] | None = None) -> None:
        self._period = period
        self._palette = [hex_to_rgb(c) for c in (palette or MORPH_PALETTE)]

    def get_params(self) -> dict[str, Any]:
        return {"period": self._period, "palette": [rgb_to_hex(*c) for c in self._palette]}

    def _apply_params(self, **kwargs: Any) -> None:
        if "period" in kwargs:
            self._period = float(kwargs["period"])
        if "palette" in kwargs and kwargs["palette"]:
            self._palette = [hex_to_rgb(c) for c in kwargs["palette"]]

    async def start(self, adapter: DeviceAdapter, params: Params) -> None:
        brightness = float(params.get("brightness", 1.0))
        palette = [_hsbk(c, brightness) for c in params.get("palette", MORPH_PALETTE)]
        await _matrix(adapter).start_tile_effect(
            TileEffectType.MORPH, _period_ms(params, self._period), palette
        )

    def emulate(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        drift = ctx.t / (self._period * 4.0)
        swirl = 0.15 * np.sin(2.0 * math.pi * (ctx.t / self._period) + leds.local_u * 6.0)
        position = leds.npos[:, 0] * 0.6 + leds.npos[:, 2] * 0.4 + drift + swirl
        return _cyclic(self._palette, position.astype(np.float64))


class LifxMove(FirmwareEffect):
    display_name = "LIFX Move"

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "period": EffectParam(
                type="float", default=8.0, min=1.0, max=30.0, step=0.5, label="Speed"
            ),
            "reverse": EffectParam(type="bool", default=False, label="Reverse"),
            "palette": _palette_param(MOVE_PALETTE),
        }

    def __init__(
        self, period: float = 8.0, reverse: bool = False, palette: list[str] | None = None
    ) -> None:
        self._period = period
        self._reverse = reverse
        self._palette = [hex_to_rgb(c) for c in (palette or MOVE_PALETTE)]

    def get_params(self) -> dict[str, Any]:
        return {
            "period": self._period,
            "reverse": self._reverse,
            "palette": [rgb_to_hex(*c) for c in self._palette],
        }

    def _apply_params(self, **kwargs: Any) -> None:
        if "period" in kwargs:
            self._period = float(kwargs["period"])
        if "reverse" in kwargs:
            self._reverse = bool(kwargs["reverse"])
        if "palette" in kwargs and kwargs["palette"]:
            self._palette = [hex_to_rgb(c) for c in kwargs["palette"]]

    def supports(self, caps: DeviceCapabilities) -> bool:
        return caps.protocol == "LIFX" and caps.multizone

    async def start(self, adapter: DeviceAdapter, params: Params) -> None:
        strip = _multizone(adapter)
        brightness = float(params.get("brightness", 1.0))
        palette = [hex_to_rgb(c) for c in params.get("palette", MOVE_PALETTE)]
        count = strip.led_count
        positions = np.arange(count, dtype=np.float64) / max(1, count)
        gradient = _loop(palette, positions)
        await strip.set_zone_colours(
            [_hsbk((int(r), int(g), int(b)), brightness) for r, g, b in gradient]
        )
        await strip.start_multizone_effect(
            MultiZoneEffectType.MOVE,
            _period_ms(params, self._period),
            reverse=bool(params.get("reverse", self._reverse)),
        )

    async def stop(self, adapter: DeviceAdapter) -> None:
        await _multizone(adapter).start_multizone_effect(MultiZoneEffectType.OFF, 0)

    async def is_running(self, adapter: DeviceAdapter) -> bool | None:
        state = await _multizone(adapter).multizone_effect()
        return None if state is None else state.effect == MultiZoneEffectType.MOVE

    def emulate(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        direction = -1.0 if self._reverse else 1.0
        position = leds.local_u.astype(np.float64) - direction * ctx.t / self._period
        return _cyclic(self._palette, position)


class LifxWaveform(FirmwareEffect):
    display_name = "LIFX waveform"

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "period": EffectParam(
                type="float", default=4.0, min=0.5, max=20.0, step=0.5, label="Speed"
            ),
            "colour": EffectParam(type="color", default="#ff6a00", label="Colour"),
            "base": EffectParam(type="color", default="#1a0033", label="Base"),
            "waveform": EffectParam(
                type="choice", default="sine", choices=list(WAVEFORMS), label="Shape"
            ),
        }

    def __init__(
        self,
        period: float = 4.0,
        colour: str = "#ff6a00",
        base: str = "#1a0033",
        waveform: str = "sine",
    ) -> None:
        self._period = period
        self._colour = colour
        self._base = base
        self._waveform = waveform

    def get_params(self) -> dict[str, Any]:
        return {
            "period": self._period,
            "colour": self._colour,
            "base": self._base,
            "waveform": self._waveform,
        }

    def _apply_params(self, **kwargs: Any) -> None:
        if "period" in kwargs:
            self._period = float(kwargs["period"])
        if "colour" in kwargs:
            self._colour = str(kwargs["colour"])
        if "base" in kwargs:
            self._base = str(kwargs["base"])
        if "waveform" in kwargs:
            self._waveform = str(kwargs["waveform"])

    def supports(self, caps: DeviceCapabilities) -> bool:
        return caps.protocol == "LIFX" and caps.colour

    async def start(self, adapter: DeviceAdapter, params: Params) -> None:
        light = _lifx(adapter)
        brightness = float(params.get("brightness", 1.0))
        await light.set_colour(_hsbk(str(params.get("base", self._base)), brightness))
        await light.set_waveform(
            _hsbk(str(params.get("colour", self._colour)), brightness),
            _period_ms(params, self._period),
            WAVEFORM_CYCLES,
            WAVEFORMS[str(params.get("waveform", self._waveform))],
            transient=True,
        )

    async def stop(self, adapter: DeviceAdapter) -> None:
        # Any SetColor interrupts a waveform.
        await _lifx(adapter).set_colour(_hsbk(self._base, 1.0))

    async def is_running(self, adapter: DeviceAdapter) -> bool | None:
        return None  # LIFX can't report a running waveform

    def emulate(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        p = (ctx.t / self._period) % 1.0
        shape = self._waveform
        if shape == "triangle":
            v = 1.0 - abs(2.0 * p - 1.0)
        elif shape == "saw":
            v = p
        elif shape == "half_sine":
            v = math.sin(math.pi * p)
        elif shape == "pulse":
            v = 1.0 if p < 0.5 else 0.0
        else:
            v = 0.5 - 0.5 * math.cos(2.0 * math.pi * p)
        base = np.array(hex_to_rgb(self._base), dtype=np.float32)
        target = np.array(hex_to_rgb(self._colour), dtype=np.float32)
        out = np.empty((leds.count, 3), dtype=np.float32)
        out[:] = (base + (target - base) * np.float32(v)) / np.float32(255.0)
        return out
