from __future__ import annotations

from typing import TYPE_CHECKING

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.capabilities import LightReading
from dj_ledfx.devices.govee.protocol import (
    build_brightness_message,
    build_solid_color_message,
    build_turn_message,
)
from dj_ledfx.devices.govee.state import GoveeDeviceState
from dj_ledfx.devices.govee.types import GoveeDeviceRecord

if TYPE_CHECKING:
    from dj_ledfx.devices.govee.transport import GoveeTransport

STATUS_TIMEOUT_S = 1.0


class GoveeAdapterBase(DeviceAdapter):
    """Shared base for Govee adapters: connect, power, reads, capture and restore."""

    supports_latency_probing = False

    def __init__(self, transport: GoveeTransport, record: GoveeDeviceRecord) -> None:
        self._transport = transport
        self._record = record
        self._is_connected = False

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    async def connect(self) -> None:
        """Check the lamp answers, when its replies can reach us. Changes nothing on it."""
        if self._transport.can_receive:
            status = await self._transport.query_status(self._record.ip)
            if status is None:
                msg = f"Govee device {self._record.ip} ({self._record.sku}) not reachable"
                raise ConnectionError(msg)
        self._is_connected = True

    async def disconnect(self) -> None:
        self._is_connected = False

    async def _status(self) -> GoveeDeviceState | None:
        if not self._transport.can_receive:
            return None
        status = await self._transport.query_status(self._record.ip, timeout_s=STATUS_TIMEOUT_S)
        return GoveeDeviceState.from_status(status) if status is not None else None

    async def read_light(self) -> LightReading:
        state = await self._status()
        if state is None:  # HA holds UDP 4002, or no status came back: it can't say
            return LightReading.UNKNOWN
        return LightReading(power=bool(state.on_off), colour=(state.r, state.g, state.b))

    async def set_power(self, on: bool) -> None:
        await self._transport.send_command(self._record.ip, build_turn_message(on=on))

    async def prepare_stream(self) -> None:
        await self._transport.send_command(self._record.ip, build_brightness_message(100))

    async def capture_state(self) -> bytes | None:
        state = await self._status()
        return state.to_bytes() if state is not None else None

    async def restore_state(self, state: bytes, *, power: bool = True) -> None:
        if not power:  # a LAN colour command may switch the lamp on: leave it as it is
            return
        saved = GoveeDeviceState.from_bytes(state)
        ip = self._record.ip
        await self._transport.send_command(
            ip, build_solid_color_message(saved.r, saved.g, saved.b)
        )
        await self._transport.send_command(ip, build_brightness_message(saved.brightness))
        # Turn off last so colour and brightness are set while the lamp is still on
        if not saved.on_off:
            await self._transport.send_command(ip, build_turn_message(on=False))
