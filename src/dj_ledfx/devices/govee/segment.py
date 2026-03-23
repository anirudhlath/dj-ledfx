from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from loguru import logger
from numpy.typing import NDArray

from dj_ledfx.devices.govee.adapter_base import GoveeAdapterBase
from dj_ledfx.devices.govee.protocol import (
    build_pt_real_message,
    build_segment_color_packet,
    build_solid_color_message,
    encode_segment_mask,
    map_colors_to_segments,
)
from dj_ledfx.devices.govee.types import GoveeDeviceRecord
from dj_ledfx.spatial.geometry import DeviceGeometry, StripGeometry
from dj_ledfx.types import DeviceInfo

if TYPE_CHECKING:
    from dj_ledfx.devices.govee.transport import GoveeTransport


class GoveeSegmentAdapter(GoveeAdapterBase):
    def __init__(
        self,
        transport: GoveeTransport,
        record: GoveeDeviceRecord,
        num_segments: int,
        *,
        use_pt_real: bool = False,
    ) -> None:
        super().__init__(transport, record)
        self._num_segments = num_segments
        self._use_pt_real = use_pt_real

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
        return StripGeometry(direction=(1, 0, 0), length=1.0)

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        segment_colors = map_colors_to_segments(colors, self._num_segments)

        if self._use_pt_real:
            ble_packets: list[bytes] = []
            for i, (r, g, b) in enumerate(segment_colors):
                mask = encode_segment_mask([i], self._num_segments)
                ble_packets.append(build_segment_color_packet(r, g, b, mask))
            msg = build_pt_real_message(ble_packets)
        else:
            avg = colors.mean(axis=0).astype(np.uint8)
            msg = build_solid_color_message(int(avg[0]), int(avg[1]), int(avg[2]))

        try:
            await self._transport.send_command(self._record.ip, msg)
        except OSError:
            self._is_connected = False
            logger.warning("Govee send_frame failed for {}", self._record.ip)
