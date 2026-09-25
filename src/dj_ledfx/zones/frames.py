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
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Literal, Protocol

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.scheduling.route import to_device_colors

if TYPE_CHECKING:
    from dj_ledfx.zones.runtime import ZoneRuntime

Stream = Literal["live", "preview"]
STREAMS: tuple[Stream, ...] = ("live", "preview")


class Watchers:
    """Which streams each session watches. A session is keyed by its subscription object,
    which lives as long as the session and clears itself when the session ends."""

    def __init__(self) -> None:
        self._streams: dict[int, frozenset[str]] = {}

    def set(self, owner: object, streams: Iterable[str]) -> None:
        wanted = frozenset(stream for stream in streams if stream in STREAMS)
        if wanted:
            self._streams[id(owner)] = wanted
        else:
            self._streams.pop(id(owner), None)

    def clear(self, owner: object) -> None:
        self._streams.pop(id(owner), None)

    def watching(self) -> bool:
        return bool(self._streams)

    def watching_live(self) -> bool:
        return any("live" in streams for streams in self._streams.values())

    def watching_preview(self) -> bool:
        return any("preview" in streams for streams in self._streams.values())


class _LiveRuntimes(Protocol):
    def live_runtimes(self) -> list[ZoneRuntime]: ...


class _PreviewRuntimes(Protocol):
    def runtimes(self) -> list[ZoneRuntime]: ...


class FrameFeed:
    def __init__(
        self,
        zones: _LiveRuntimes,
        previews: _PreviewRuntimes | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._zones = zones
        self._previews = previews
        self._clock = clock  # the engine's clock: rings are keyed by time.monotonic()

    def frames(self, stream: Stream) -> dict[str, NDArray[np.uint8]]:
        """Each device's colours now, in 8 bits, by device id."""
        if stream == "live":
            runtimes = self._zones.live_runtimes()
        else:
            runtimes = self._previews.runtimes() if self._previews is not None else []
        now = self._clock()
        out: dict[str, NDArray[np.uint8]] = {}
        for runtime in runtimes:
            frame = runtime.ring.find_nearest(now)
            if frame is None:
                continue
            for light in runtime.lights:
                piece = runtime.leds.slice_for(light.device_id)
                if piece is None or piece.count == 0 or frame.colors.shape[0] < piece.stop:
                    continue
                colors = frame.colors[piece.start : piece.stop]
                out[light.device_id] = to_device_colors(colors, piece.count)
        return out
