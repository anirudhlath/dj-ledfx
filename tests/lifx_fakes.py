"""A stand-in for LifxTransport that answers requests the way a LIFX light does."""

from __future__ import annotations

import struct
from collections.abc import Collection, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from dj_ledfx.devices.lifx.bulb import LifxBulbAdapter
from dj_ledfx.devices.lifx.packet import (
    GET_COLOR,
    GET_DEVICE_CHAIN,
    GET_EXTENDED_COLOR_ZONES,
    GET_HOST_FIRMWARE,
    GET_MULTIZONE_EFFECT,
    GET_TILE_EFFECT,
    GET_VERSION,
    HSBK,
    LIGHT_STATE,
    SET_COLOR,
    SET_EXTENDED_COLOR_ZONES,
    SET_LIGHT_POWER,
    SET_MULTIZONE_EFFECT,
    SET_TILE_EFFECT,
    SET_WAVEFORM,
    STATE_DEVICE_CHAIN,
    STATE_EXTENDED_COLOR_ZONES,
    STATE_HOST_FIRMWARE,
    STATE_LIGHT_POWER,
    STATE_MULTIZONE_EFFECT,
    STATE_TILE_EFFECT,
    STATE_UNHANDLED,
    STATE_VERSION,
    LifxPacket,
)
from dj_ledfx.devices.lifx.strip import LifxStripAdapter
from dj_ledfx.devices.lifx.tile_chain import LifxTileChainAdapter
from dj_ledfx.devices.lifx.transport import LifxTransport
from dj_ledfx.devices.lifx.types import TileInfo
from dj_ledfx.types import DeviceInfo

if TYPE_CHECKING:
    from dj_ledfx.devices.capabilities import DeviceCapabilities


class FakeLifxTransport(LifxTransport):
    """Records every packet. Requests get the reply a light would send, or None when silent.

    Only the socket is faked (send_packet, request_response); asking, parsing and the
    queries are LifxTransport's own. It never opens and never probes.
    """

    def __init__(
        self,
        *,
        power: bool = True,
        hsbk: HSBK = (0, 0, 65535, 3500),
        label: str = "Lamp",
        zones: Sequence[HSBK] = (),
        product: int = 1,
        firmware: tuple[int, int] = (3, 70),
        chain: Sequence[tuple[int, int]] = (),
        unhandled: Collection[int] = (),
        silent: bool = False,
    ) -> None:
        super().__init__()
        self._source_id = 4242
        self._is_open = True
        self.power = power
        self.hsbk = hsbk
        self.label = label
        self.zones: list[HSBK] = list(zones)
        self.product = product
        self.firmware = firmware
        self.chain = list(chain)  # (width, height) per tile
        self.tile_effect: tuple[int, int, tuple[HSBK, ...]] = (0, 0, ())
        self.multizone_effect: tuple[int, int, bool] = (0, 0, False)
        self.unhandled = set(unhandled)
        self.silent = silent
        self.sent: list[LifxPacket] = []

    def send_packet(self, packet: LifxPacket, addr: tuple[str, int]) -> None:
        self.sent.append(packet)
        self._apply(packet)

    async def request_response(
        self,
        packet: LifxPacket,
        addr: tuple[str, int],
        response_type: int | Collection[int],
        timeout: float = 1.0,
    ) -> LifxPacket | None:
        self.sent.append(packet)
        if self.silent:
            return None
        if packet.msg_type in self.unhandled:
            return self._reply(STATE_UNHANDLED, struct.pack("<H", packet.msg_type))
        self._apply(packet)
        return self._state_for(packet.msg_type)

    def start_probing(self, interval_s: float = 2.0) -> None:
        pass  # the real one would send echo requests from a background task

    def types(self) -> list[int]:
        return [packet.msg_type for packet in self.sent]

    def last(self, msg_type: int) -> LifxPacket:
        return [packet for packet in self.sent if packet.msg_type == msg_type][-1]

    def _apply(self, packet: LifxPacket) -> None:
        payload = packet.payload
        if packet.msg_type == SET_COLOR:
            hue, sat, bri, kelvin = struct.unpack("<4H", payload[1:9])
            self.hsbk = (hue, sat, bri, kelvin)
        elif packet.msg_type == SET_LIGHT_POWER:
            (level,) = struct.unpack("<H", payload[:2])
            self.power = level != 0
        elif packet.msg_type == SET_TILE_EFFECT:
            (speed,) = struct.unpack("<I", payload[7:11])
            palette: list[HSBK] = []
            for index in range(payload[59]):
                hue, sat, bri, kelvin = struct.unpack(
                    "<4H", payload[60 + index * 8 : 68 + index * 8]
                )
                palette.append((hue, sat, bri, kelvin))
            self.tile_effect = (payload[6], speed, tuple(palette))
        elif packet.msg_type == SET_MULTIZONE_EFFECT:
            (speed,) = struct.unpack("<I", payload[7:11])
            (direction,) = struct.unpack("<I", payload[31:35])
            self.multizone_effect = (payload[4], speed, direction == 0)
        elif packet.msg_type == SET_EXTENDED_COLOR_ZONES:
            _duration, _mode, index, count = struct.unpack("<IBHB", payload[:8])
            while len(self.zones) < index + count:
                self.zones.append((0, 0, 0, 3500))
            for offset in range(count):
                start = 8 + offset * 8
                hue, sat, bri, kelvin = struct.unpack("<4H", payload[start : start + 8])
                self.zones[index + offset] = (hue, sat, bri, kelvin)

    def _state_for(self, msg_type: int) -> LifxPacket | None:
        if msg_type in (GET_COLOR, SET_COLOR, SET_WAVEFORM):
            label = self.label.encode()[:32]
            power = 65535 if self.power else 0
            state = struct.pack("<4H2sH32s8s", *self.hsbk, b"", power, label, b"")
            return self._reply(LIGHT_STATE, state)
        if msg_type == SET_LIGHT_POWER:
            return self._reply(STATE_LIGHT_POWER, struct.pack("<H", 65535 if self.power else 0))
        if msg_type in (GET_TILE_EFFECT, SET_TILE_EFFECT):
            effect, speed, palette = self.tile_effect
            colours = b"".join(struct.pack("<4H", *c) for c in palette)
            state = (
                struct.pack("<BIBIQII", 0, 1, effect, speed, 0, 0, 0)
                + bytes(32)
                + bytes([len(palette)])
                + colours.ljust(128, b"\x00")
            )
            return self._reply(STATE_TILE_EFFECT, state)
        if msg_type in (GET_MULTIZONE_EFFECT, SET_MULTIZONE_EFFECT):
            effect, speed, reverse = self.multizone_effect
            state = (
                struct.pack("<IBHIQII", 1, effect, 0, speed, 0, 0, 0)
                + struct.pack("<II", 0, 0 if reverse else 1)
                + bytes(24)
            )
            return self._reply(STATE_MULTIZONE_EFFECT, state)
        if msg_type in (GET_EXTENDED_COLOR_ZONES, SET_EXTENDED_COLOR_ZONES):
            shown = self.zones[:82]
            colours = b"".join(struct.pack("<4H", *c) for c in shown)
            state = struct.pack("<HHB", len(self.zones), 0, len(shown)) + colours.ljust(
                656, b"\x00"
            )
            return self._reply(STATE_EXTENDED_COLOR_ZONES, state)
        if msg_type == GET_DEVICE_CHAIN:
            entries = b"".join(
                struct.pack(
                    "<hhh2sffBBBII4sQ8sHH4s",
                    0,
                    0,
                    0,
                    b"",
                    float(index),
                    0.0,
                    width,
                    height,
                    0,
                    1,
                    self.product,
                    b"",
                    0,
                    b"",
                    0,
                    0,
                    b"",
                )
                for index, (width, height) in enumerate(self.chain)
            )
            state = b"\x00" + entries.ljust(16 * 55, b"\x00") + bytes([len(self.chain)])
            return self._reply(STATE_DEVICE_CHAIN, state)
        if msg_type == GET_HOST_FIRMWARE:
            major, minor = self.firmware
            return self._reply(STATE_HOST_FIRMWARE, struct.pack("<QQHH", 0, 0, minor, major))
        if msg_type == GET_VERSION:
            return self._reply(STATE_VERSION, struct.pack("<III", 1, self.product, 0))
        return None

    def _reply(self, msg_type: int, payload: bytes) -> LifxPacket:
        return LifxPacket(
            tagged=False,
            source=self.source_id,
            target=b"\x00" * 8,
            ack_required=False,
            res_required=False,
            sequence=0,
            msg_type=msg_type,
            payload=payload,
        )


MAC = b"\xd0\x73\xd5\x00\x00\x01"


def lifx_info(kind: str, leds: int) -> DeviceInfo:
    return DeviceInfo(
        f"LIFX {kind}",
        f"lifx_{kind}",
        leds,
        "10.0.0.5:56700",
        mac=MAC.hex(),
        stable_id=f"lifx:{MAC.hex()}",
        backend="lifx",
    )


def lifx_bulb(transport: FakeLifxTransport) -> LifxBulbAdapter:
    return LifxBulbAdapter(transport, lifx_info("bulb", 1), MAC)


def lifx_strip(transport: FakeLifxTransport, zones: int = 8) -> LifxStripAdapter:
    return LifxStripAdapter(transport, lifx_info("strip", zones), MAC, zone_count=zones)


def lifx_candle(
    transport: FakeLifxTransport, caps: DeviceCapabilities | None = None
) -> LifxTileChainAdapter:
    """A Candle C: one 5x6 matrix."""
    tile = TileInfo(user_x=0.0, user_y=0.0, width=5, height=6, accel_x=0, accel_y=0, accel_z=0)
    return LifxTileChainAdapter(transport, lifx_info("tile", 30), MAC, tiles=[tile], caps=caps)


def read_hex(path: Path) -> bytes:
    """A hex fixture: hex digits over any number of lines, "#" lines are comments."""
    lines = path.read_text().splitlines()
    return bytes.fromhex("".join(line for line in lines if not line.startswith("#")))
