# Pro DJ Link protocol constants
# Reference: https://djl-analysis.deepsymmetry.org/djl-analysis/beats.html

# Network
PRODJLINK_PORT = 50001  # Beat/sync broadcast port (passive, no handshake)
STATUS_PORT = 50002  # Status port (requires virtual CDJ — not used in MVP)

# Packet header
MAGIC_HEADER = b"Qspt1WmJOL"  # 10 bytes, all Pro DJ Link packets start with this
MAGIC_HEADER_LEN = 10

# Packet type byte (offset 0x0A, after magic header)
PACKET_TYPE_BEAT = 0x28  # Beat packet

# Beat packet structure (96 bytes total)
BEAT_PACKET_LEN = 96

# Byte offsets within beat packet (after magic header)
OFFSET_PACKET_TYPE = 0x0A  # 1 byte: packet type
OFFSET_DEVICE_NAME = 0x0B  # 20 bytes: device name (null-padded ASCII)
OFFSET_DEVICE_NUMBER = 0x21  # 1 byte: player/device number (1-6)
OFFSET_NEXT_BEAT_MS = 0x24  # 4 bytes: ms until next beat (big-endian uint32)
OFFSET_SECOND_BEAT_MS = 0x28  # 4 bytes: ms until 2nd next beat
OFFSET_NEXT_BAR_MS = 0x34  # 4 bytes: ms until next bar downbeat
OFFSET_BPM = 0x5A  # 2 bytes: BPM × 100 (big-endian uint16), e.g., 12800 = 128.00
OFFSET_PITCH = 0x54  # 4 bytes: pitch adjustment (see below)
OFFSET_BEAT_NUMBER = 0x5C  # 1 byte: beat within bar (1-4)

# Pitch encoding: value is centered at 0x00100000 (1048576)
# pitch_percent = (raw - 1048576) / 10485.76
PITCH_CENTER = 0x00100000
PITCH_SCALE = 10485.76

# Capability byte for CDJ-3000 generation
CAPABILITY_CDJ3000 = 0x1F
OFFSET_CAPABILITY = 0x1F  # 1 byte (between device name and device number)
