"""A Govee lamp playing one colour (engine spec §6.3), on any number of segments: each frame
goes out as its average colour by colorwc, which the backend sends at most GOVEE_COLOUR_FPS
times a second (config.py)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.devices.govee.adapter_base import GoveeAdapterBase
from dj_ledfx.devices.govee.protocol import build_razer_switch, build_solid_color_message


class GoveeColourAdapter(GoveeAdapterBase):
    """One colour by colorwc: a lamp of one segment, one the SKU table doesn't know, or one
    set to play one colour."""

    async def _stream(self, colors: NDArray[np.uint8]) -> None:
        r, g, b = (int(c) for c in colors.mean(axis=0).astype(np.uint8))
        await self._send(build_solid_color_message(r, g, b))

    async def prepare_stream(self) -> None:
        """Out of razer, in case a look left the lamp there, then full brightness."""
        await self._send(build_razer_switch(on=False))
        await super().prepare_stream()
