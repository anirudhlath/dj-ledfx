"""OpenRGB hardware modes as a firmware effect (spec §6.3)."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import numpy as np

from dj_ledfx.devices.capabilities import DeviceCapabilities, FirmwareRejected
from dj_ledfx.devices.openrgb import OpenRGBAdapter
from dj_ledfx.effects.color import hsv_to_rgb_array
from dj_ledfx.effects.firmware import FirmwareEffect, Params
from dj_ledfx.effects.params import EffectParam

if TYPE_CHECKING:
    from dj_ledfx.devices.adapter import DeviceAdapter
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

PREFERRED_MODES = ("Rainbow Wave", "Spectrum Cycle", "Rainbow", "Breathing")
COPY_PERIOD_S = 8.0


def _openrgb(adapter: DeviceAdapter) -> OpenRGBAdapter:
    if not isinstance(adapter, OpenRGBAdapter):
        raise FirmwareRejected(f"{adapter.device_info.name} isn't an OpenRGB device")
    return adapter


class OpenrgbMode(FirmwareEffect):
    display_name = "OpenRGB mode"

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "mode": EffectParam(
                type="choice", default="auto", choices=["auto", *PREFERRED_MODES], label="Mode"
            )
        }

    def __init__(self, mode: str = "auto") -> None:
        self._mode = mode

    def get_params(self) -> dict[str, Any]:
        return {"mode": self._mode}

    def _apply_params(self, **kwargs: Any) -> None:
        if "mode" in kwargs:
            self._mode = str(kwargs["mode"])

    def chosen_mode(self, caps: DeviceCapabilities, wanted: str | None = None) -> str | None:
        """The device's own name for the mode to run, or None if it has none of them."""
        available = {name.lower(): name for name in caps.openrgb_modes}
        mode = wanted or self._mode
        for name in PREFERRED_MODES if mode == "auto" else (mode,):
            if name.lower() in available:
                return available[name.lower()]
        return None

    def supports(self, caps: DeviceCapabilities) -> bool:
        return caps.protocol == "OpenRGB" and self.chosen_mode(caps) is not None

    async def start(self, adapter: DeviceAdapter, params: Params) -> None:
        device = _openrgb(adapter)
        mode = self.chosen_mode(device.capabilities, str(params.get("mode", self._mode)))
        if mode is None:
            raise FirmwareRejected(f"{device.device_info.name} has none of {PREFERRED_MODES}")
        await device.set_mode(mode, float(params.get("brightness", 1.0)))

    async def stop(self, adapter: DeviceAdapter) -> None:
        await _openrgb(adapter).prepare_stream()

    async def is_running(self, adapter: DeviceAdapter) -> bool | None:
        device = _openrgb(adapter)
        mode = self.chosen_mode(device.capabilities)
        active = await device.active_mode_name()
        if mode is None or active is None:
            return None
        return active.lower() == mode.lower()

    def emulate(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        if self._mode == "Breathing":
            level = 0.5 - 0.5 * math.cos(2.0 * math.pi * ctx.t / COPY_PERIOD_S)
            out = np.zeros((leds.count, 3), dtype=np.float32)
            out[:, 0] = np.float32(level)
            return out
        hues = np.mod(leds.local_u.astype(np.float64) - ctx.t / COPY_PERIOD_S, 1.0)
        out = hsv_to_rgb_array(hues, 1.0, 1.0).astype(np.float32)
        out *= np.float32(1.0 / 255.0)
        return out
