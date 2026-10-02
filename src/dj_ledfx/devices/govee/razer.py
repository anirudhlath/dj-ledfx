"""A Govee lamp playing razer (engine spec §6.3): each frame lights every segment on its own,
at the configured rate."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.devices.govee.adapter_base import GoveeAdapterBase
from dj_ledfx.devices.govee.protocol import build_razer_frame, build_razer_switch
from dj_ledfx.devices.govee.types import GoveeDeviceRecord, GoveeForm

if TYPE_CHECKING:
    from dj_ledfx.devices.govee.transport import GoveeTransport

# A frame after a pause this long switches razer on again first: a lamp may drop out of
# razer mode when frames stop (the light-output plan's Task 8 checks how soon).
RAZER_IDLE_S = 2.0


class GoveeRazerAdapter(GoveeAdapterBase):
    """Razer frames, one colour per segment. Razer is switched on before the first frame,
    after RAZER_IDLE_S without one, and again after a prepare, restore or power switch."""

    razer = True

    def __init__(
        self,
        transport: GoveeTransport,
        record: GoveeDeviceRecord,
        segments: int,
        *,
        form: GoveeForm = "strip",
        from_top: bool = False,
        connected: bool = False,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(
            transport, record, segments, form=form, from_top=from_top, connected=connected
        )
        self._clock = clock
        self._last_frame_at: float | None = None  # None: razer is switched on first

    async def _stream(self, colors: NDArray[np.uint8]) -> None:
        now = self._clock()
        if self._last_frame_at is None or now - self._last_frame_at > RAZER_IDLE_S:
            await self._send(build_razer_switch(on=True))
        await self._send(build_razer_frame(colors))
        self._last_frame_at = now

    async def set_power(self, on: bool) -> None:
        self._last_frame_at = None  # a lamp switched may come back out of razer mode
        await super().set_power(on)

    async def prepare_stream(self) -> None:
        """Full brightness; the next frame switches razer on."""
        self._last_frame_at = None
        await super().prepare_stream()

    async def restore_state(self, state: bytes, *, power: bool = True) -> None:
        """As the base class does; the next frame switches razer on again."""
        self._last_frame_at = None
        await super().restore_state(state, power=power)
