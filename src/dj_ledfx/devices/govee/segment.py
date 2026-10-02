"""A Govee lamp with segments (engine spec §6.3). In razer mode each frame lights every
segment on its own; otherwise the frame's average colour goes out by colorwc, which the
backend sends at most GOVEE_COLOUR_FPS times a second (config.py)."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TYPE_CHECKING

import numpy as np
from loguru import logger
from numpy.typing import NDArray

from dj_ledfx.devices.govee.adapter_base import GoveeAdapterBase
from dj_ledfx.devices.govee.protocol import (
    build_razer_frame,
    build_razer_switch,
    build_solid_color_message,
)
from dj_ledfx.devices.govee.types import GoveeDeviceRecord, GoveeForm
from dj_ledfx.spatial.geometry import DeviceGeometry, StripGeometry
from dj_ledfx.types import DeviceInfo

if TYPE_CHECKING:
    from dj_ledfx.devices.govee.transport import GoveeTransport

# A frame after a pause this long switches razer on again first: a lamp may drop out of
# razer mode when frames stop (the light-output plan's Task 8 checks how soon).
RAZER_IDLE_S = 2.0
UPRIGHT_HEIGHT_M = 1.4  # an upright lamp's segments, bottom to top
STRIP_LENGTH_M = 1.0


class GoveeSegmentAdapter(GoveeAdapterBase):
    def __init__(
        self,
        transport: GoveeTransport,
        record: GoveeDeviceRecord,
        num_segments: int,
        *,
        razer: bool = False,
        form: GoveeForm = "strip",
        from_top: bool = False,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(transport, record)
        self._num_segments = num_segments
        self._razer = razer
        self._form = form
        self._from_top = from_top
        self._clock = clock
        self._last_frame_at: float | None = None  # None: razer is switched on first

    @property
    def razer(self) -> bool:
        """True: each frame lights every segment on its own. False: one colour."""
        return self._razer

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            name=f"Govee {self._record.sku} ({self._record.ip})",
            device_type="govee_segment",
            led_count=self._num_segments,
            address=f"{self._record.ip}:4003",
            stable_id=f"govee:{self._record.device_id}",
            backend="govee",
        )

    @property
    def led_count(self) -> int:
        return self._num_segments

    @property
    def geometry(self) -> DeviceGeometry:
        """An upright lamp stands, segment 0 at the bottom (or the top); another lies along
        its length. Directions are the scene's: y is up."""
        if self._form == "upright":
            up = -1 if self._from_top else 1
            return StripGeometry(direction=(0, up, 0), length=UPRIGHT_HEIGHT_M)
        return StripGeometry(direction=(1, 0, 0), length=STRIP_LENGTH_M)

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        try:
            if self._razer:
                await self._send_razer(colors)
            else:
                avg = colors.mean(axis=0).astype(np.uint8)
                msg = build_solid_color_message(int(avg[0]), int(avg[1]), int(avg[2]))
                await self._transport.send_command(self._record.ip, msg)
        except OSError:
            self._is_connected = False
            logger.warning("Govee send_frame failed for {}", self._record.ip)

    async def _send_razer(self, colors: NDArray[np.uint8]) -> None:
        now = self._clock()
        if self._last_frame_at is None or now - self._last_frame_at > RAZER_IDLE_S:
            await self._transport.send_command(self._record.ip, build_razer_switch(on=True))
        await self._transport.send_command(self._record.ip, build_razer_frame(colors))
        self._last_frame_at = now

    async def set_power(self, on: bool) -> None:
        self._last_frame_at = None  # a lamp switched may come back out of razer mode
        await super().set_power(on)

    async def prepare_stream(self) -> None:
        """Full brightness; the next frame switches razer on. A lamp playing one colour is
        taken out of razer mode, in case a look left it there."""
        self._last_frame_at = None
        if not self._razer:
            await self._transport.send_command(self._record.ip, build_razer_switch(on=False))
        await super().prepare_stream()

    async def restore_state(self, state: bytes, *, power: bool = True) -> None:
        """Out of razer mode first, so the lamp shows the colour it gets back. A lamp
        switched off elsewhere (power=False) is left alone, as the base class does."""
        self._last_frame_at = None
        if self._razer and power:
            await self._transport.send_command(self._record.ip, build_razer_switch(on=False))
        await super().restore_state(state, power=power)
