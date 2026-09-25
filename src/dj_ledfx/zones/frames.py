"""The web app's frames (spec §4.1; web spec §12.4), and who watches them.

Frames are read from each runtime's ring when a client asks for them, never made by the
routed send loops (M1 review, constraint 2). The live stream is what each zone light shows
now, whether it is sent to the light or not; the preview stream is the preview runtime's.
Watchers says which streams any WebSocket session watches: a zone draws the lights that
run their own effect only for the web app, so only while the live stream is watched
(constraint 3), and a preview nobody watches ends (Review Focus 1).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Collection, Iterable
from typing import TYPE_CHECKING, Literal

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.scheduling.route import slice_colors

if TYPE_CHECKING:
    from dj_ledfx.zones.runtime import ZoneRuntime

Stream = Literal["live", "preview"]
STREAMS: tuple[Stream, ...] = ("live", "preview")


class Watchers:
    """Which streams each session watches. A session is keyed by its subscription object,
    which lives as long as the session and sets no streams when the session ends."""

    def __init__(self) -> None:
        self._streams: dict[int, frozenset[str]] = {}

    def set(self, owner: object, streams: Iterable[str]) -> None:
        wanted = frozenset(stream for stream in streams if stream in STREAMS)
        if wanted:
            self._streams[id(owner)] = wanted
        else:
            self._streams.pop(id(owner), None)

    def watching(self, stream: Stream) -> bool:
        """Whether any session watches the stream. main hands the zones and the previews
        partial(watching, "live") and partial(watching, "preview")."""
        return any(stream in streams for streams in self._streams.values())


Runtimes = Callable[[], list["ZoneRuntime"]]


class FrameFeed:
    def __init__(
        self,
        live: Runtimes,
        previews: Runtimes = list,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._runtimes: dict[Stream, Runtimes] = {"live": live, "preview": previews}
        self._clock = clock  # the engine's clock: rings are keyed by time.monotonic()

    def frames(
        self, stream: Stream, wanted: Collection[str] | None = None
    ) -> dict[str, NDArray[np.uint8]]:
        """Each device's colours now, in 8 bits, by device id: every device's, or the wanted
        ones'. A runtime's frame is converted once, and only when a device in it is wanted."""
        now = self._clock()
        out: dict[str, NDArray[np.uint8]] = {}
        for runtime in self._runtimes[stream]():
            pieces = [
                piece
                for light in runtime.lights
                if wanted is None or light.device_id in wanted
                if (piece := runtime.leds.slice_for(light.device_id)) is not None and piece.count
            ]
            frame = runtime.ring.find_nearest(now) if pieces else None
            if frame is None:
                continue
            count = runtime.leds.count
            whole = slice_colors(frame.colors, 0, count, count)
            if whole is None:
                continue
            for piece in pieces:
                out[piece.device_id] = whole[piece.start : piece.stop]
        return out
