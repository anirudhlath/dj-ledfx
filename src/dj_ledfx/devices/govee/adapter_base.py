"""A Govee lamp (engine spec §6.3): what its two outputs share. `GoveeRazerAdapter` lights
each segment on its own by razer; `GoveeColourAdapter` sends one colour by colorwc."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

import numpy as np
from loguru import logger
from numpy.typing import NDArray

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.capabilities import DeviceCapabilities, LightReading, NoAnswer
from dj_ledfx.devices.govee.protocol import (
    build_brightness_message,
    build_razer_switch,
    build_solid_color_message,
    build_turn_message,
)
from dj_ledfx.devices.govee.state import GoveeDeviceState
from dj_ledfx.devices.govee.types import GoveeDeviceRecord, GoveeForm
from dj_ledfx.spatial.geometry import DeviceGeometry, PointGeometry, StripGeometry
from dj_ledfx.types import DeviceInfo

if TYPE_CHECKING:
    from dj_ledfx.devices.govee.transport import GoveeTransport

STATUS_TIMEOUT_S = 1.0
# A reply lost on the LAN isn't a lamp gone (a streaming lamp answered 9 queries of 10), so
# a status read asks again once before it counts as silence, as LIFX reads do.
STATUS_TRIES = 2
UPRIGHT_HEIGHT_M = 1.4  # an upright lamp's segments, bottom to top
STRIP_LENGTH_M = 1.0


class GoveeAdapterBase(DeviceAdapter):
    """Shared base for Govee adapters: connect, power, reads, capture and restore, and where
    the lamp's segments sit. A subclass streams a frame through `_stream`."""

    supports_latency_probing = False
    razer: ClassVar[bool] = False  # True: each frame lights every segment on its own

    def __init__(
        self,
        transport: GoveeTransport,
        record: GoveeDeviceRecord,
        segments: int = 1,
        *,
        form: GoveeForm = "strip",
        from_top: bool = False,
    ) -> None:
        self._transport = transport
        self._record = record
        self._segments = segments
        self._form = form
        self._from_top = from_top
        self._is_connected = False

    @property
    def device_info(self) -> DeviceInfo:
        """Its device type is what rows and the API have always held: govee_segment for a
        lamp of segments, govee_solid for a lamp of one."""
        return DeviceInfo(
            name=f"Govee {self._record.sku} ({self._record.ip})",
            device_type="govee_segment" if self._segments > 1 else "govee_solid",
            led_count=self._segments,
            address=f"{self._record.ip}:4003",
            stable_id=f"govee:{self._record.device_id}",
            backend="govee",
        )

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def last_heard(self) -> float | None:
        return self._transport.last_heard(self._record.ip)

    @property
    def led_count(self) -> int:
        return self._segments

    @property
    def geometry(self) -> DeviceGeometry:
        """One segment is a point. An upright lamp stands, segment 0 at the bottom (or the
        top); another lies along its length. Directions are the scene's: y is up."""
        if self._segments == 1:
            return PointGeometry()
        if self._form == "upright":
            up = -1 if self._from_top else 1
            return StripGeometry(direction=(0, up, 0), length=UPRIGHT_HEIGHT_M)
        return StripGeometry(direction=(1, 0, 0), length=STRIP_LENGTH_M)

    @property
    def capabilities(self) -> DeviceCapabilities:
        """The model is "Govee <model number>"; multizone when it has segments to light."""
        sku = self._record.sku
        return DeviceCapabilities(
            protocol="Govee",
            model=f"Govee {sku}" if sku else "Govee",
            multizone=self.led_count > 1,
        )

    async def connect(self) -> None:
        """Check the lamp answers, when its replies can reach us. Changes nothing on it."""
        if self._transport.can_receive and await self._status() is None:
            msg = f"Govee device {self._record.ip} ({self._record.sku}) not reachable"
            raise ConnectionError(msg)
        self._is_connected = True

    async def disconnect(self) -> None:
        self._is_connected = False

    async def _send(self, message: dict[str, Any]) -> None:
        await self._transport.send_command(self._record.ip, message)

    async def _status(self) -> GoveeDeviceState | None:
        """The lamp's status, asked up to STATUS_TRIES times. None: it stayed silent, or no
        reply can reach us."""
        if not self._transport.can_receive:
            return None
        for _try in range(STATUS_TRIES):
            status = await self._transport.query_status(
                self._record.ip, timeout_s=STATUS_TIMEOUT_S
            )
            if status is not None:
                return GoveeDeviceState.from_status(status)
        return None

    async def read_light(self) -> LightReading:
        """Power and colour from a status query. Unknown while another program holds UDP
        4002, since no reply can reach us; NoAnswer when the lamp stays silent, which the
        light monitor counts as a missed read."""
        if not self._transport.can_receive:
            return LightReading.UNKNOWN
        state = await self._status()
        if state is None:
            raise NoAnswer(f"Govee {self._record.ip} didn't answer a status query")
        return LightReading(power=bool(state.on_off), colour=(state.r, state.g, state.b))

    async def set_power(self, on: bool) -> None:
        await self._send(build_turn_message(on=on))

    async def prepare_stream(self) -> None:
        await self._send(build_brightness_message(100))

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        try:
            await self._stream(colors)
        except OSError:
            self._is_connected = False
            logger.warning("Govee send_frame failed for {}", self._record.ip)

    @abstractmethod
    async def _stream(self, colors: NDArray[np.uint8]) -> None:
        """Send one frame, one colour per segment."""

    async def capture_state(self) -> bytes | None:
        state = await self._status()
        return state.to_bytes() if state is not None else None

    async def restore_state(self, state: bytes, *, power: bool = True) -> None:
        """Put the lamp back as captured, out of razer first so it shows the colour it gets
        back. A lamp switched off elsewhere (power=False) is left alone: a LAN colour
        command may switch it on."""
        if not power:
            return
        saved = GoveeDeviceState.from_bytes(state)
        await self._send(build_razer_switch(on=False))
        await self._send(build_solid_color_message(saved.r, saved.g, saved.b))
        await self._send(build_brightness_message(saved.brightness))
        # Turn off last so colour and brightness are set while the lamp is still on
        if not saved.on_off:
            await self._send(build_turn_message(on=False))
