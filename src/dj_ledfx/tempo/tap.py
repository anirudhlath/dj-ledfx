"""Tap tempo (web spec §6.2: "the BPM updates within one tap after the third").

A tap's time is the client's own clock when it sends one (web spec §12.4's `client_time`,
in seconds), so the network's delays never reach the BPM, and the time it arrived when
it doesn't. One run of taps never mixes the two. A client time is a hint, not a setting:
one the clock can't use times the tap by its arrival (usable_client_time).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from dj_ledfx.tempo.model import MAX_BPM, MIN_BPM
from dj_ledfx.types import is_finite_number

GAP_S = 60.0 / MIN_BPM  # a pause longer than the slowest beat starts a new run
MIN_INTERVAL_S = 60.0 / MAX_BPM  # taps closer than the fastest beat are one tap
MAX_INTERVALS = 8  # the tempo is the mean of the run's last eight intervals
BPM_FROM_TAP = 3  # the run's third tap sets the BPM
MAX_CLIENT_SKEW_S = 86_400.0  # a client clock further than a day from the server's is wrong


def usable_client_time(client_time: object, server_time: float) -> float | None:
    """A tap's client time, seconds since the epoch, or None to time the tap by its
    arrival: when it's missing, not a finite number, or more than a day from the server's
    clock (`server_time`). A person who taps always gets their tap."""
    if not is_finite_number(client_time) or abs(client_time - server_time) > MAX_CLIENT_SKEW_S:
        return None
    return float(client_time)


@dataclass(frozen=True, slots=True)
class Tap:
    index: int  # 0 for a run's first tap
    at: float  # when it happened, on the server's time.monotonic()
    bpm: float | None  # the run's tempo, from its third tap


class TapTempo:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._stamps: list[float] = []
        self._client = False
        self._index = -1
        self._offset = 0.0  # client time to server time, from the least-delayed tap
        self._arrived = -math.inf

    def tap(self, arrived: float, client_time: float | None = None) -> Tap | None:
        """The tap that arrived at `arrived`, or None for one the run can't use: a
        second tap within MIN_INTERVAL_S of the last, or one stamped before it.
        `client_time` is a usable_client_time(), or None."""
        client = client_time is not None
        stamp = float(client_time) if client_time is not None and client else arrived
        last = self._stamps[-1] if self._stamps else None
        if (
            last is None
            or client != self._client
            or arrived - self._arrived > GAP_S
            or abs(stamp - last) > GAP_S
        ):
            self.reset()
            self._client = client
            self._offset = arrived - stamp
        elif stamp - last < MIN_INTERVAL_S:
            return None
        self._stamps = [*self._stamps[-MAX_INTERVALS:], stamp]
        self._index += 1
        self._arrived = arrived
        self._offset = min(self._offset, arrived - stamp)
        bpm = None
        if self._index + 1 >= BPM_FROM_TAP:
            span = self._stamps[-1] - self._stamps[0]
            bpm = min(max(60.0 * (len(self._stamps) - 1) / span, MIN_BPM), MAX_BPM)
        return Tap(self._index, stamp + self._offset, bpm)
