"""Play razer (DreamView) patterns on one Govee lamp for the owner to judge by eye, then put
the lamp back as it was (the light-output plan's Task 8).

Patterns, at GOVEE_RAZER_FPS frames a second:
  whole    the whole lamp red, green, then blue, 2 s each: does it take razer frames at all?
  ends     segment 0 red, the last segment blue, the rest dim, 5 s: which end is segment 0?
  stripes  every other segment red, on blue, 5 s: does every segment show?
  chase    one white segment running from the first to the last, 10 s: order and smoothness
  gaps     2 s each of red, green, blue and white, after pauses of 1, 2 and 3 s, with razer
           switched on only at the start: does the lamp leave razer mode in a pause?
  status   the chase, asking the lamp's status once a second: does it still answer? It binds
           UDP 4002, so it runs only while the deployed app is stopped.

It sends no brightness, and binds no port except for status. From the repo root:

    uv run python scripts/govee_razer_check.py --ip ADDRESS --segments 15 --pattern ends \\
        --restore-colour RRGGBB --restore-power on
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from typing import Any

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.config import GOVEE_RAZER_FPS
from dj_ledfx.devices.govee.protocol import (
    build_razer_frame,
    build_razer_switch,
    build_solid_color_message,
    build_status_query,
    build_turn_message,
)
from dj_ledfx.devices.govee.transport import COMMAND_PORT, RESPONSE_PORT
from dj_ledfx.effects.color import hex_to_rgb
from dj_ledfx.types import RGB

PATTERNS = ("whole", "ends", "stripes", "chase", "gaps", "status")
RED: RGB = (255, 0, 0)
GREEN: RGB = (0, 255, 0)
BLUE: RGB = (0, 0, 255)
WHITE: RGB = (255, 255, 255)
DIM: RGB = (40, 40, 40)
Frame = NDArray[np.uint8] | None  # None: a pause, nothing sent


def _solid(segments: int, colour: RGB) -> NDArray[np.uint8]:
    return np.tile(np.array(colour, dtype=np.uint8), (segments, 1))


def frames(pattern: str, segments: int) -> list[Frame]:
    """The pattern's frames, one every 1/GOVEE_RAZER_FPS s."""
    fps = GOVEE_RAZER_FPS
    out: list[Frame] = []
    if pattern == "whole":
        for colour in (RED, GREEN, BLUE):
            out += [_solid(segments, colour)] * (2 * fps)
    elif pattern == "ends":
        frame = _solid(segments, DIM)
        frame[0], frame[-1] = RED, BLUE
        out += [frame] * (5 * fps)
    elif pattern == "stripes":
        frame = _solid(segments, BLUE)
        frame[::2] = RED
        out += [frame] * (5 * fps)
    elif pattern in ("chase", "status"):
        steps = 10 * fps
        for step in range(steps):
            frame = np.zeros((segments, 3), dtype=np.uint8)
            frame[step * segments // steps] = WHITE
            out.append(frame)
    elif pattern == "gaps":
        for colour, pause_s in ((RED, 1), (GREEN, 2), (BLUE, 3), (WHITE, 0)):
            out += [_solid(segments, colour)] * (2 * fps)
            out += [None] * (pause_s * fps)
    else:
        raise ValueError(f"Unknown pattern {pattern!r}: one of {', '.join(PATTERNS)}")
    return out


def _send(sock: socket.socket, ip: str, message: dict[str, Any]) -> None:
    sock.sendto(json.dumps(message).encode(), (ip, COMMAND_PORT))


def _bind_replies() -> socket.socket:
    replies = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        replies.bind(("0.0.0.0", RESPONSE_PORT))
    except OSError:
        replies.close()
        sys.exit(f"UDP {RESPONSE_PORT} is held (the deployed app?): stop it first")
    replies.setblocking(False)
    return replies


def _count_replies(replies: socket.socket, ip: str) -> int:
    """The lamp's status replies waiting on the socket."""
    count = 0
    while True:
        try:
            data, (sender, _port) = replies.recvfrom(4096)
        except BlockingIOError:
            return count
        if sender == ip and b"devStatus" in data:
            count += 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--ip", required=True, help="the lamp's address")
    parser.add_argument("--segments", type=int, required=True)
    parser.add_argument("--pattern", choices=PATTERNS, required=True)
    parser.add_argument("--restore-colour", required=True, help="RRGGBB: its colour before")
    parser.add_argument("--restore-power", choices=("on", "off"), required=True)
    args = parser.parse_args()
    r, g, b = hex_to_rgb(args.restore_colour)
    replies = _bind_replies() if args.pattern == "status" else None
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    before = during = asked = 0
    try:
        if args.restore_power == "off":
            _send(sock, args.ip, build_turn_message(on=True))
            time.sleep(1.0)
        if replies is not None:
            for _ in range(5):
                _send(sock, args.ip, build_status_query())
                time.sleep(1.0)
            before = _count_replies(replies, args.ip)
        _send(sock, args.ip, build_razer_switch(on=True))
        start = time.monotonic()
        for index, frame in enumerate(frames(args.pattern, args.segments)):
            if frame is not None:
                _send(sock, args.ip, build_razer_frame(frame))
            if replies is not None and index % GOVEE_RAZER_FPS == 0:
                _send(sock, args.ip, build_status_query())
                asked += 1
            time.sleep(max(0.0, start + (index + 1) / GOVEE_RAZER_FPS - time.monotonic()))
        if replies is not None:
            time.sleep(1.0)
            during = _count_replies(replies, args.ip)
    finally:
        _send(sock, args.ip, build_razer_switch(on=False))
        time.sleep(0.2)
        _send(sock, args.ip, build_solid_color_message(r, g, b))
        if args.restore_power == "off":
            time.sleep(0.2)
            _send(sock, args.ip, build_turn_message(on=False))
        sock.close()
        if replies is not None:
            replies.close()
    if replies is not None:
        print(f"status replies: {before}/5 before razer, {during}/{asked} during")
    print("restored")


if __name__ == "__main__":
    main()
