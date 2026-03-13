from __future__ import annotations

import struct
from dataclasses import dataclass

HEADER_SIZE = 36
PROTOCOL = 1024


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
            size,                    # 0-1: size
            flags,                   # 2-3: flags
            self.source,             # 4-7: source
            self.target,             # 8-15: target
            b"\x00" * 6,            # 16-21: reserved
            ack_res,                 # 22: ack/res flags
            self.sequence & 0xFF,    # 23: sequence
            b"\x00" * 8,            # 24-31: reserved
            self.msg_type,           # 32-33: type
            0,                       # 34-35: reserved
        )
        return header + self.payload

    @classmethod
    def unpack(cls, data: bytes) -> LifxPacket:
        if len(data) < HEADER_SIZE:
            raise ValueError(f"Packet too short: {len(data)} < {HEADER_SIZE}")
        (
            size, flags, source, target, _reserved,
            ack_res, sequence, _reserved2, msg_type, _reserved3,
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
