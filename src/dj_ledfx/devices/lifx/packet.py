from __future__ import annotations

import colorsys
import struct
from collections.abc import Sequence
from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from dj_ledfx.devices.lifx.types import TileInfo

HEADER_SIZE = 36
PROTOCOL = 1024

# --- Message types (LIFX LAN protocol) ---
GET_HOST_FIRMWARE = 14
STATE_HOST_FIRMWARE = 15
GET_VERSION = 32
STATE_VERSION = 33
GET_COLOR = 101
SET_COLOR = 102
SET_WAVEFORM = 103
LIGHT_STATE = 107
SET_LIGHT_POWER = 117
STATE_LIGHT_POWER = 118
STATE_UNHANDLED = 223
GET_MULTIZONE_EFFECT = 507
SET_MULTIZONE_EFFECT = 508
STATE_MULTIZONE_EFFECT = 509
SET_EXTENDED_COLOR_ZONES = 510
GET_EXTENDED_COLOR_ZONES = 511
STATE_EXTENDED_COLOR_ZONES = 512
GET_DEVICE_CHAIN = 701
STATE_DEVICE_CHAIN = 702
SET_TILE_STATE_64 = 715
GET_TILE_EFFECT = 718
SET_TILE_EFFECT = 719
STATE_TILE_EFFECT = 720

HSBK = tuple[int, int, int, int]
TILE_EFFECT_PALETTE_MAX = 16
DEVICE_CHAIN_SLOTS = 16
TILE_ENTRY_SIZE = 55


class TileEffectType(IntEnum):
    OFF = 0
    MORPH = 2
    FLAME = 3
    SKY = 5


class MultiZoneEffectType(IntEnum):
    OFF = 0
    MOVE = 1


class Waveform(IntEnum):
    SAW = 0
    SINE = 1
    HALF_SINE = 2
    TRIANGLE = 3
    PULSE = 4


@dataclass(frozen=True, slots=True)
class TileEffectState:
    instance_id: int
    effect: int  # a TileEffectType value; unknown values are kept as they are
    speed_ms: int
    palette: tuple[HSBK, ...]


@dataclass(frozen=True, slots=True)
class MultiZoneEffectState:
    instance_id: int
    effect: int  # a MultiZoneEffectType value
    speed_ms: int
    reverse: bool


@dataclass
class LifxPacket:
    tagged: bool
    source: int
    target: bytes  # 8 bytes (6-byte MAC + 2 padding)
    ack_required: bool
    res_required: bool
    sequence: int
    msg_type: int
    payload: bytes

    def pack(self) -> bytes:
        size = HEADER_SIZE + len(self.payload)
        # Byte 2-3: origin(2)=0 | tagged(1) | addressable(1)=1 | protocol(12)=1024
        flags = PROTOCOL
        flags |= 0x1000  # addressable
        if self.tagged:
            flags |= 0x2000
        # Byte 22: reserved(6) | ack_required(1) | res_required(1)
        ack_res = 0
        if self.ack_required:
            ack_res |= 0x02
        if self.res_required:
            ack_res |= 0x01

        header = struct.pack(
            "<HHI8s6sBB8sHH",
            size,  # 0-1: size
            flags,  # 2-3: flags
            self.source,  # 4-7: source
            self.target,  # 8-15: target
            b"\x00" * 6,  # 16-21: reserved
            ack_res,  # 22: ack/res flags
            self.sequence & 0xFF,  # 23: sequence
            b"\x00" * 8,  # 24-31: reserved
            self.msg_type,  # 32-33: type
            0,  # 34-35: reserved
        )
        return header + self.payload

    @classmethod
    def unpack(cls, data: bytes) -> LifxPacket:
        if len(data) < HEADER_SIZE:
            raise ValueError(f"Packet too short: {len(data)} < {HEADER_SIZE}")
        (
            size,
            flags,
            source,
            target,
            _reserved,
            ack_res,
            sequence,
            _reserved2,
            msg_type,
            _reserved3,
        ) = struct.unpack("<HHI8s6sBB8sHH", data[:HEADER_SIZE])
        return cls(
            tagged=bool(flags & 0x2000),
            source=source,
            target=target,
            ack_required=bool(ack_res & 0x02),
            res_required=bool(ack_res & 0x01),
            sequence=sequence,
            msg_type=msg_type,
            payload=data[HEADER_SIZE:size],
        )


# --- Payload builders ---


def build_set_color(hsbk: tuple[int, int, int, int], duration_ms: int = 0) -> bytes:
    """Build SetColor(102) payload. 13 bytes."""
    return struct.pack("<B4HI", 0, *hsbk, duration_ms)


def build_get_color() -> bytes:
    """Build GetColor(101) payload. Empty (0 bytes)."""
    return b""


def parse_light_state(payload: bytes) -> tuple[int, int, int, int, int, str]:
    """Parse LightState(107) → (hue, saturation, brightness, kelvin, power, label).

    Payload layout (52 bytes minimum):
      [0:2]   hue (uint16 LE)
      [2:4]   saturation (uint16 LE)
      [4:6]   brightness (uint16 LE)
      [6:8]   kelvin (uint16 LE)
      [8:10]  reserved
      [10:12] power (uint16 LE, 0=off, 65535=on)
      [12:44] label (32 bytes, null-terminated UTF-8)
    """
    if len(payload) < 44:
        raise ValueError(f"LightState payload too short: {len(payload)} < 44")
    h, s, b, k = struct.unpack("<4H", payload[:8])
    power = struct.unpack("<H", payload[10:12])[0]
    label = payload[12:44].split(b"\x00", 1)[0].decode("utf-8", errors="replace")
    return h, s, b, k, power, label


def build_echo_request(payload: bytes) -> bytes:
    """Build EchoRequest(58) payload. Must be exactly 64 bytes."""
    return payload[:64].ljust(64, b"\x00")


def build_set_tile_state64(
    tile_index: int,
    length: int,
    x: int,
    y: int,
    width: int,
    duration_ms: int,
    colors: list[tuple[int, int, int, int]],
) -> bytes:
    """Build SetTileState64(715) payload. ~522 bytes."""
    header = struct.pack("<BBBBBBI", tile_index, length, 0, x, y, width, duration_ms)
    color_data = b"".join(struct.pack("<4H", *c) for c in colors[:64])
    color_data = color_data.ljust(64 * 8, b"\x00")
    return header + color_data


def build_set_extended_color_zones(
    duration_ms: int,
    apply: int,
    zone_index: int,
    count: int,
    colors: list[tuple[int, int, int, int]],
) -> bytes:
    """Build SetExtendedColorZones(510) payload. Fixed 664 bytes (82 zones)."""
    header = struct.pack("<IBHB", duration_ms, apply, zone_index, count)
    color_data = b"".join(struct.pack("<4H", *c) for c in colors[:82])
    color_data = color_data.ljust(82 * 8, b"\x00")
    return header + color_data


def build_set_tile_effect(
    effect: TileEffectType,
    speed_ms: int,
    palette: Sequence[HSBK] = (),
    *,
    instance_id: int = 0,
    duration_ns: int = 0,
) -> bytes:
    """SetTileEffect(719) payload, 188 bytes. Flame ignores the palette; Morph uses it."""
    colors = list(palette)[:TILE_EFFECT_PALETTE_MAX]
    head = struct.pack("<BBIBIQII", 0, 0, instance_id, int(effect), speed_ms, duration_ns, 0, 0)
    body = b"".join(struct.pack("<4H", *c) for c in colors)
    return (
        head
        + bytes(32)
        + struct.pack("<B", len(colors))
        + body.ljust(TILE_EFFECT_PALETTE_MAX * 8, b"\x00")
    )


def build_get_tile_effect() -> bytes:
    """GetTileEffect(718) payload: two reserved bytes."""
    return b"\x00\x00"


def build_set_multizone_effect(
    effect: MultiZoneEffectType,
    speed_ms: int,
    *,
    reverse: bool = False,
    instance_id: int = 0,
    duration_ns: int = 0,
) -> bytes:
    """SetMultiZoneEffect(508) payload, 59 bytes. Move's direction: 0 reversed, 1 forward."""
    parameters = struct.pack("<II", 0, 0 if reverse else 1) + bytes(24)
    head = struct.pack("<IBHIQII", instance_id, int(effect), 0, speed_ms, duration_ns, 0, 0)
    return head + parameters


def build_set_waveform(
    hsbk: HSBK,
    period_ms: int,
    cycles: float,
    waveform: Waveform,
    *,
    transient: bool = True,
    skew_ratio: float = 0.5,
) -> bytes:
    """SetWaveform(103) payload, 21 bytes. skew_ratio 0..1 is PULSE's duty cycle."""
    skew = max(-32768, min(32767, round(skew_ratio * 65535) - 32768))
    return struct.pack(
        "<BB4HIfhB", 0, int(transient), *hsbk, period_ms, cycles, skew, int(waveform)
    )


def build_set_light_power(on: bool, duration_ms: int = 0) -> bytes:
    """SetLightPower(117) payload, 6 bytes."""
    return struct.pack("<HI", 65535 if on else 0, duration_ms)


# --- Payload parsers ---


def parse_state_service(payload: bytes) -> tuple[int, int]:
    """Parse StateService(3) → (service, port)."""
    service, port = struct.unpack("<BI", payload[:5])
    return service, port


def parse_state_version(payload: bytes) -> tuple[int, int, int]:
    """Parse StateVersion(33) → (vendor, product, version)."""
    return struct.unpack("<III", payload[:12])


def parse_echo_response(payload: bytes) -> bytes:
    """Parse EchoResponse(59) → echo payload."""
    return payload[:64]


def parse_state_extended_color_zones(payload: bytes) -> tuple[int, int, list[HSBK]]:
    """StateExtendedColorZones(512): zones_count, zone_index, colors_count, then 82 colours."""
    if len(payload) < 5:
        raise ValueError(f"StateExtendedColorZones payload too short: {len(payload)} < 5")
    zone_count, zone_index, colors_count = struct.unpack("<HHB", payload[:5])
    colors: list[HSBK] = []
    for index in range(min(colors_count, 82)):
        start = 5 + index * 8
        if start + 8 > len(payload):
            break
        hue, sat, bri, kelvin = struct.unpack("<4H", payload[start : start + 8])
        colors.append((hue, sat, bri, kelvin))
    return int(zone_count), int(zone_index), colors


def parse_state_device_chain(payload: bytes) -> list[TileInfo]:
    """StateDeviceChain(702): start_index, 16 tile slots of 55 bytes, then the tile count."""
    from dj_ledfx.devices.lifx.types import TileInfo as TileInfoCls

    expected = 1 + DEVICE_CHAIN_SLOTS * TILE_ENTRY_SIZE + 1
    if len(payload) < expected:
        raise ValueError(f"StateDeviceChain payload too short: {len(payload)} < {expected}")
    count = min(payload[expected - 1], DEVICE_CHAIN_SLOTS)
    tiles: list[TileInfoCls] = []
    for index in range(count):
        start = 1 + index * TILE_ENTRY_SIZE
        entry = payload[start : start + TILE_ENTRY_SIZE]
        accel_x, accel_y, accel_z = struct.unpack("<hhh", entry[0:6])
        user_x, user_y = struct.unpack("<ff", entry[8:16])
        tiles.append(
            TileInfoCls(
                user_x=user_x,
                user_y=user_y,
                width=entry[16],
                height=entry[17],
                accel_x=accel_x,
                accel_y=accel_y,
                accel_z=accel_z,
            )
        )
    return tiles


def parse_state_tile_effect(payload: bytes) -> TileEffectState:
    """StateTileEffect(720), 187 bytes."""
    if len(payload) < 187:
        raise ValueError(f"StateTileEffect payload too short: {len(payload)} < 187")
    _reserved, instance_id, effect, speed_ms, _duration, _r1, _r2 = struct.unpack(
        "<BIBIQII", payload[:26]
    )
    count = min(payload[58], TILE_EFFECT_PALETTE_MAX)
    palette: list[HSBK] = []
    for index in range(count):
        start = 59 + index * 8
        hue, sat, bri, kelvin = struct.unpack("<4H", payload[start : start + 8])
        palette.append((hue, sat, bri, kelvin))
    return TileEffectState(int(instance_id), int(effect), int(speed_ms), tuple(palette))


def parse_state_multizone_effect(payload: bytes) -> MultiZoneEffectState:
    """StateMultiZoneEffect(509), 59 bytes."""
    if len(payload) < 59:
        raise ValueError(f"StateMultiZoneEffect payload too short: {len(payload)} < 59")
    instance_id, effect, _r, speed_ms, _duration, _r1, _r2 = struct.unpack(
        "<IBHIQII", payload[:27]
    )
    (direction,) = struct.unpack("<I", payload[31:35])
    return MultiZoneEffectState(
        int(instance_id), int(effect), int(speed_ms), reverse=direction == 0
    )


def parse_state_host_firmware(payload: bytes) -> tuple[int, int]:
    """StateHostFirmware(15) -> (major, minor)."""
    _build, _reserved, minor, major = struct.unpack("<QQHH", payload[:20])
    return int(major), int(minor)


# --- Color conversion ---


def rgb_to_hsbk(
    r: int,
    g: int,
    b: int,
    kelvin: int = 3500,
) -> tuple[int, int, int, int]:
    """Convert single RGB (0-255) to LIFX HSBK (0-65535)."""
    rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
    cmax = max(rf, gf, bf)
    cmin = min(rf, gf, bf)
    delta = cmax - cmin

    # Hue
    if delta == 0:
        hue = 0.0
    elif cmax == rf:
        hue = 60.0 * (((gf - bf) / delta) % 6)
    elif cmax == gf:
        hue = 60.0 * (((bf - rf) / delta) + 2)
    else:
        hue = 60.0 * (((rf - gf) / delta) + 4)

    # Saturation
    sat = 0.0 if cmax == 0 else delta / cmax

    # Brightness
    bri = cmax

    h = int(hue / 360.0 * 65535) & 0xFFFF
    s = int(sat * 65535) & 0xFFFF
    v = int(bri * 65535) & 0xFFFF
    return (h, s, v, kelvin)


def hsbk_to_rgb(hsbk: HSBK) -> tuple[int, int, int]:
    """LIFX HSBK to 8-bit RGB. Kelvin is ignored, so a white shows as plain white."""
    hue, sat, bri, _kelvin = hsbk
    red, green, blue = colorsys.hsv_to_rgb(hue / 65535, sat / 65535, bri / 65535)
    return round(red * 255), round(green * 255), round(blue * 255)


def rgb_array_to_hsbk(
    colors: NDArray[np.uint8],
    kelvin: int = 3500,
) -> NDArray[np.uint16]:
    """Vectorized RGB (N,3) uint8 → HSBK (N,4) uint16. Pure numpy, no loops."""
    f = colors.astype(np.float32) / 255.0
    r, g, b = f[:, 0], f[:, 1], f[:, 2]

    cmax = f.max(axis=1)
    cmin = f.min(axis=1)
    delta = cmax - cmin

    # Hue (piecewise)
    hue = np.zeros(len(colors), dtype=np.float32)
    mask_r = (cmax == r) & (delta > 0)
    mask_g = (cmax == g) & (delta > 0) & ~mask_r
    mask_b = (delta > 0) & ~mask_r & ~mask_g

    hue[mask_r] = 60.0 * (((g[mask_r] - b[mask_r]) / delta[mask_r]) % 6)
    hue[mask_g] = 60.0 * (((b[mask_g] - r[mask_g]) / delta[mask_g]) + 2)
    hue[mask_b] = 60.0 * (((r[mask_b] - g[mask_b]) / delta[mask_b]) + 4)

    # Saturation
    with np.errstate(invalid="ignore"):
        sat = np.where(cmax > 0, delta / cmax, 0.0)

    # Build output
    result = np.zeros((len(colors), 4), dtype=np.uint16)
    result[:, 0] = (hue / 360.0 * 65535).astype(np.uint16)
    result[:, 1] = (sat * 65535).astype(np.uint16)
    result[:, 2] = (cmax * 65535).astype(np.uint16)
    result[:, 3] = kelvin
    return result
