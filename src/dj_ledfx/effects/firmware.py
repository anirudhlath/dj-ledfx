"""Firmware effects ask a light to run one of its own built-in effects (spec §5.1)."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, ClassVar

from dj_ledfx.effects.base import Effect

if TYPE_CHECKING:
    from dj_ledfx.devices.adapter import DeviceAdapter
    from dj_ledfx.devices.capabilities import DeviceCapabilities
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

Params = Mapping[str, Any]


class FirmwareEffect(Effect):
    display_name: ClassVar[str] = ""  # the light's "own effect" name, e.g. "LIFX Flame"

    @abstractmethod
    def supports(self, caps: DeviceCapabilities) -> bool: ...

    @abstractmethod
    async def start(self, adapter: DeviceAdapter, params: Params) -> None:
        """Start (or restart) the effect. Raise FirmwareRejected if the light refuses."""

    @abstractmethod
    async def stop(self, adapter: DeviceAdapter) -> None: ...

    @abstractmethod
    async def is_running(self, adapter: DeviceAdapter) -> bool | None:
        """Whether the light still runs it; None when the protocol can't say."""

    @abstractmethod
    def emulate(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        """A streamed copy for lights that can't run it, and what the preview shows."""

    def start_params(self, brightness: float) -> dict[str, Any]:
        """What start() receives: this layer's settings plus the zone brightness (0-1)."""
        return {**self.get_params(), "brightness": brightness}
