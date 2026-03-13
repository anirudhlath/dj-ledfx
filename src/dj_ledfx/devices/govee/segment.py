from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from loguru import logger
from numpy.typing import NDArray

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.govee.protocol import (
    build_brightness_message,
    build_pt_real_message,
    build_segment_color_packet,
    build_turn_message,
    encode_segment_mask,
    map_colors_to_segments,
)
from dj_ledfx.devices.govee.types import GoveeDeviceRecord
from dj_ledfx.types import DeviceInfo

if TYPE_CHECKING:
    from dj_ledfx.devices.govee.transport import GoveeTransport


class GoveeSegmentAdapter(DeviceAdapter):
    supports_latency_probing = False

    def __init__(
        self, transport: GoveeTransport, record: GoveeDeviceRecord, num_segments: int
    ) -> None:
        self._transport = transport
        self._record = record
        self._num_segments = num_segments
        self._is_connected = False

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            name=f"Govee {self._record.sku} ({self._record.ip})",
            device_type="govee_segment",
            led_count=self._num_segments,
            address=f"{self._record.ip}:4003",
        )

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def led_count(self) -> int:
        return self._num_segments

    async def connect(self) -> None:
        status = await self._transport.query_status(self._record.ip)
        if status is None:
            msg = f"Govee device {self._record.ip} ({self._record.sku}) not reachable"
            raise ConnectionError(msg)
        # Ensure device is on and at full brightness for LED effects
        if not status.get("onOff"):
            logger.info("Turning on Govee device {}", self._record.ip)
            await self._transport.send_command(self._record.ip, build_turn_message(on=True))
        await self._transport.send_command(self._record.ip, build_brightness_message(100))
        self._is_connected = True

    async def disconnect(self) -> None:
        self._is_connected = False

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        segment_colors = map_colors_to_segments(colors, self._num_segments)

        ble_packets: list[bytes] = []
        for i, (r, g, b) in enumerate(segment_colors):
            mask = encode_segment_mask([i], self._num_segments)
            ble_packets.append(build_segment_color_packet(r, g, b, mask))

        msg = build_pt_real_message(ble_packets)
        try:
            await self._transport.send_command(self._record.ip, msg)
        except OSError:
            self._is_connected = False
            logger.warning("Govee send_frame failed for {}", self._record.ip)
