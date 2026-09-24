"""What every LIFX adapter shares: packets, confirmed commands, power, colour reads,
capture and restore (spec §6.3, §7.1, §8)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, ClassVar

from loguru import logger

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.capabilities import DeviceCapabilities, FirmwareRejected, LightReading
from dj_ledfx.devices.lifx.packet import (
    GET_COLOR,
    HSBK,
    LIGHT_STATE,
    SET_COLOR,
    SET_LIGHT_POWER,
    SET_WAVEFORM,
    STATE_LIGHT_POWER,
    STATE_UNHANDLED,
    LifxPacket,
    Waveform,
    build_set_color,
    build_set_light_power,
    build_set_waveform,
    hsbk_to_rgb,
    parse_light_state,
)
from dj_ledfx.types import DeviceInfo

if TYPE_CHECKING:
    from dj_ledfx.devices.lifx.transport import LifxTransport

CAPTURE_VERSION = 1
RESTORE_FADE_MS = 500


def hsbk_from_json(values: object) -> HSBK:
    """An HSBK saved as a JSON list. Raises ValueError when it isn't one."""
    if not isinstance(values, list) or len(values) != 4:
        raise ValueError(f"not an HSBK: {values!r}")
    hue, sat, bri, kelvin = (int(v) for v in values)
    return hue, sat, bri, kelvin


class LifxAdapterBase(DeviceAdapter):
    supports_latency_probing = False
    # Where a capture keeps the light's own firmware effect; None: it has none (bulbs).
    _effect_key: ClassVar[str | None] = None

    def __init__(
        self,
        transport: LifxTransport,
        device_info: DeviceInfo,
        target_mac: bytes,
        *,
        kelvin: int,
        caps: DeviceCapabilities,
    ) -> None:
        self._transport = transport
        self._device_info = device_info
        self._target_mac = target_mac
        self._kelvin = kelvin
        self._caps = caps
        self._is_connected = False
        host, port = device_info.address.rsplit(":", 1)
        self._addr = (host, int(port))

    @property
    def device_info(self) -> DeviceInfo:
        return self._device_info

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def capabilities(self) -> DeviceCapabilities:
        return self._caps

    async def connect(self) -> None:
        self._is_connected = True

    async def disconnect(self) -> None:
        self._is_connected = False

    # --- packets ---

    def _send(self, msg_type: int, payload: bytes = b"") -> None:
        """Fire and forget: streamed frames."""
        packet = LifxPacket(
            tagged=False,
            source=self._transport.source_id,
            target=self._target_mac + b"\x00\x00",
            ack_required=False,
            res_required=False,
            sequence=self._transport.next_sequence() % 256,
            msg_type=msg_type,
            payload=payload,
        )
        self._transport.send_packet(packet, self._addr)

    async def _ask(
        self, msg_type: int, payload: bytes, reply_type: int, *, timeout: float = 0.5
    ) -> LifxPacket | None:
        """Send a request and wait for its reply, retrying once. The reply may be 223."""
        request = self._transport.make_request(self._target_mac, msg_type, payload)
        for _attempt in range(2):
            reply = await self._transport.request_response(
                request, self._addr, reply_type, timeout
            )
            if reply is not None:
                return reply
        return None

    async def _command(self, msg_type: int, payload: bytes, reply_type: int) -> LifxPacket:
        """A command the light must confirm. Raises FirmwareRejected when it doesn't."""
        reply = await self._ask(msg_type, payload, reply_type)
        if reply is None:
            raise FirmwareRejected(f"{self._device_info.name} didn't answer message {msg_type}")
        if reply.msg_type == STATE_UNHANDLED:
            raise FirmwareRejected(f"{self._device_info.name} doesn't support message {msg_type}")
        return reply

    # --- reading ---

    async def _light_state(self) -> tuple[HSBK, bool, str] | None:
        reply = await self._ask(GET_COLOR, b"", LIGHT_STATE)
        if reply is None or reply.msg_type != LIGHT_STATE:
            return None
        try:
            hue, sat, bri, kelvin, power, label = parse_light_state(reply.payload)
        except ValueError:
            return None
        return (hue, sat, bri, kelvin), power != 0, label

    async def read_light(self) -> LightReading:
        state = await self._light_state()
        if state is None:
            return LightReading(power=None, colour=None)
        hsbk, power, _label = state
        return LightReading(power=power, colour=hsbk_to_rgb(hsbk))

    # --- control ---

    async def set_power(self, on: bool) -> None:
        await self._set_power(on, 0)

    async def _set_power(self, on: bool, duration_ms: int) -> None:
        reply = await self._ask(
            SET_LIGHT_POWER, build_set_light_power(on, duration_ms), STATE_LIGHT_POWER
        )
        if reply is None or reply.msg_type != STATE_LIGHT_POWER:
            logger.warning(
                "LIFX '{}' didn't confirm power {}", self._device_info.name, "on" if on else "off"
            )

    async def set_colour(self, hsbk: HSBK, duration_ms: int = 0) -> None:
        await self._command(SET_COLOR, build_set_color(hsbk, duration_ms), LIGHT_STATE)

    async def set_waveform(
        self,
        hsbk: HSBK,
        period_ms: int,
        cycles: float,
        waveform: Waveform,
        *,
        transient: bool = True,
        skew_ratio: float = 0.5,
    ) -> None:
        payload = build_set_waveform(
            hsbk, period_ms, cycles, waveform, transient=transient, skew_ratio=skew_ratio
        )
        await self._command(SET_WAVEFORM, payload, LIGHT_STATE)

    # --- capture and restore ---

    async def capture_state(self) -> bytes | None:
        state = await self._light_state()
        if state is None:
            logger.warning(
                "LIFX '{}' didn't answer; its state isn't captured", self._device_info.name
            )
            return None
        hsbk, power, _label = state
        snapshot: dict[str, Any] = {"v": CAPTURE_VERSION, "power": power, "hsbk": list(hsbk)}
        snapshot.update(await self._capture_extra())
        return json.dumps(snapshot).encode()

    async def restore_state(self, state: bytes, *, power: bool = True) -> None:
        """Colours, then the light's own effect, then power; power=False leaves power alone.

        A light that had no effect of its own gets the look's effect stopped first, since
        colours don't stop a Flame or a Move.
        """
        try:
            snapshot = json.loads(state)
            hsbk = hsbk_from_json(snapshot["hsbk"])
            was_on = bool(snapshot["power"])
        except (ValueError, KeyError, TypeError):
            logger.warning(
                "LIFX '{}': captured state is unreadable, leaving the light alone",
                self._device_info.name,
            )
            return
        effect = snapshot.get(self._effect_key) if self._effect_key is not None else None
        if self._effect_key is not None and not isinstance(effect, dict):
            await self.prepare_stream()
        await self._restore_colours(snapshot, hsbk)
        if isinstance(effect, dict):
            try:
                await self._start_effect(effect)
            except (FirmwareRejected, ValueError, KeyError, TypeError):
                logger.warning("LIFX '{}': couldn't restart its effect", self._device_info.name)
        if power:
            await self._set_power(was_on, RESTORE_FADE_MS)

    async def prepare_stream(self) -> None:
        """Stop the light's own effect, so streamed frames show. Bulbs have none."""
        if self._effect_key is None:
            return
        try:
            await self._stop_effect()
        except FirmwareRejected:
            logger.debug("LIFX '{}' has no effects to stop", self._device_info.name)

    async def _stop_effect(self) -> None:
        """Stop the light's own firmware effect. Lights with an _effect_key override it."""

    async def _start_effect(self, saved: dict[str, Any]) -> None:
        """Start a captured firmware effect again. Lights with an _effect_key override it;
        raises ValueError, KeyError or TypeError when the capture is unreadable."""

    async def _capture_extra(self) -> dict[str, Any]:
        """Anything beyond power and colour. Strips add zones, matrices their effect."""
        return {}

    async def _restore_colours(self, snapshot: dict[str, Any], hsbk: HSBK) -> None:
        await self._ask(SET_COLOR, build_set_color(hsbk, RESTORE_FADE_MS), LIGHT_STATE)
