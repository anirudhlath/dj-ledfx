from __future__ import annotations

import struct
from typing import TYPE_CHECKING

import numpy as np
from loguru import logger
from numpy.typing import NDArray

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.lifx.packet import (
    LifxPacket,
    build_get_color,
    build_set_color,
    parse_light_state,
    rgb_to_hsbk,
)
from dj_ledfx.spatial.geometry import DeviceGeometry, PointGeometry
from dj_ledfx.types import DeviceInfo

if TYPE_CHECKING:
    from dj_ledfx.devices.lifx.transport import LifxTransport


class LifxBulbAdapter(DeviceAdapter):
    supports_latency_probing = False

    def __init__(
        self,
        transport: LifxTransport,
        device_info: DeviceInfo,
        target_mac: bytes,
        kelvin: int = 3500,
    ) -> None:
        self._transport = transport
        self._device_info = device_info
        self._target_mac = target_mac
        self._kelvin = kelvin
        self._is_connected = False
        self._addr = (device_info.address.split(":")[0], int(device_info.address.split(":")[1]))

    @property
    def device_info(self) -> DeviceInfo:
        return self._device_info

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def led_count(self) -> int:
        return 1

    @property
    def geometry(self) -> DeviceGeometry:
        return PointGeometry()

    def _make_packet(
        self, msg_type: int, payload: bytes, *, res_required: bool = False
    ) -> LifxPacket:
        return LifxPacket(
            tagged=False,
            source=self._transport.source_id,
            target=self._target_mac + b"\x00\x00",
            ack_required=False,
            res_required=res_required,
            sequence=self._transport.next_sequence() % 256,
            msg_type=msg_type,
            payload=payload,
        )

    async def connect(self) -> None:
        self._is_connected = True

    async def disconnect(self) -> None:
        self._is_connected = False

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        r, g, b = int(colors[0, 0]), int(colors[0, 1]), int(colors[0, 2])
        hsbk = rgb_to_hsbk(r, g, b, kelvin=self._kelvin)
        pkt = self._make_packet(102, build_set_color(hsbk))
        self._transport.send_packet(pkt, self._addr)

    async def capture_state(self) -> bytes:
        """Query bulb's current HSBK + power via GetColor(101) → LightState(107)."""
        pkt = self._make_packet(101, build_get_color(), res_required=True)
        response = await self._transport.request_response(pkt, self._addr, response_type=107)
        if response is not None:
            try:
                h, s, b, k, power, _label = parse_light_state(response.payload)
                return struct.pack("<4HH", h, s, b, k, power)
            except Exception:
                logger.warning("Failed to parse LightState for '{}'", self._device_info.name)
        return await super().capture_state()

    async def restore_state(self, state: bytes) -> None:
        """Restore bulb to captured HSBK + power state."""
        if len(state) == 10:
            h, s, b, k, power = struct.unpack("<4HH", state)
            # Set color (with transition)
            pkt = self._make_packet(102, build_set_color((h, s, b, k), duration_ms=500))
            self._transport.send_packet(pkt, self._addr)
            # Set power (type 117: SetLightPower, payload = power(u16) + duration(u32))
            power_payload = struct.pack("<HI", power, 500)
            pkt = self._make_packet(117, power_payload)
            self._transport.send_packet(pkt, self._addr)
        else:
            await super().restore_state(state)
