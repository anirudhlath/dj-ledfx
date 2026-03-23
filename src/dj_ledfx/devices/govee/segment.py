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
    build_solid_color_message,
    build_turn_message,
    encode_segment_mask,
    map_colors_to_segments,
)
from dj_ledfx.devices.govee.state import GoveeDeviceState
from dj_ledfx.devices.govee.types import GoveeDeviceRecord
from dj_ledfx.spatial.geometry import DeviceGeometry, StripGeometry
from dj_ledfx.types import DeviceInfo

if TYPE_CHECKING:
    from dj_ledfx.devices.govee.transport import GoveeTransport


class GoveeSegmentAdapter(DeviceAdapter):
    supports_latency_probing = False

    def __init__(
        self,
        transport: GoveeTransport,
        record: GoveeDeviceRecord,
        num_segments: int,
        *,
        use_pt_real: bool = False,
    ) -> None:
        self._transport = transport
        self._record = record
        self._num_segments = num_segments
        self._use_pt_real = use_pt_real
        self._is_connected = False
        self._original_state: GoveeDeviceState | None = None

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
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def led_count(self) -> int:
        return self._num_segments

    @property
    def geometry(self) -> DeviceGeometry:
        return StripGeometry(direction=(1, 0, 0), length=1.0)

    async def connect(self) -> None:
        status = await self._transport.query_status(self._record.ip)
        if status is None:
            msg = f"Govee device {self._record.ip} ({self._record.sku}) not reachable"
            raise ConnectionError(msg)
        # Capture original state BEFORE modifying the device
        self._original_state = GoveeDeviceState.from_status(status)
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

        if self._use_pt_real:
            ble_packets: list[bytes] = []
            for i, (r, g, b) in enumerate(segment_colors):
                mask = encode_segment_mask([i], self._num_segments)
                ble_packets.append(build_segment_color_packet(r, g, b, mask))
            msg = build_pt_real_message(ble_packets)
        else:
            # Fallback: average all segments into a single colorwc command
            avg = colors.mean(axis=0).astype(np.uint8)
            msg = build_solid_color_message(int(avg[0]), int(avg[1]), int(avg[2]))

        try:
            await self._transport.send_command(self._record.ip, msg)
        except OSError:
            self._is_connected = False
            logger.warning("Govee send_frame failed for {}", self._record.ip)

    async def capture_state(self) -> bytes:
        if self._original_state is not None:
            return self._original_state.to_bytes()
        return await super().capture_state()

    async def restore_state(self, state: bytes) -> None:
        saved = GoveeDeviceState.from_bytes(state)
        ip = self._record.ip
        # Restore color first (while device is still on and bright)
        await self._transport.send_command(ip, build_solid_color_message(saved.r, saved.g, saved.b))
        # Restore brightness
        await self._transport.send_command(ip, build_brightness_message(saved.brightness))
        # Restore on/off last — if device was off, turn it off
        if not saved.on_off:
            await self._transport.send_command(ip, build_turn_message(on=False))
