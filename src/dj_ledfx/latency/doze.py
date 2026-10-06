"""The doze check (light-sync spec §5): a light whose Wi-Fi dozes, told by when its replies
land. The access point holds a dozing light's packets until the light wakes, at a beacon, so
its replies bunch at one phase of the beacon cycle, and its round trips run long: a query
waits for a wake, on average half a beacon, even with nothing queued."""

from __future__ import annotations

import math
import statistics
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass

# The beacon interval of every access point here, 100 TU. A light that wakes at every
# second or fourth beacon bunches in this cycle too; behind an access point whose interval
# isn't a multiple of 100 TU, a dozing light isn't recognised (spec §10).
BEACON_S = 0.1024
KEPT = 40  # the round trips the check holds: the newest that counted
MIN_REPLIES = 10  # with fewer, a light keeps the mode it has
DOZE_Z = 7.0  # an awake light turns dozing when its replies bunch this much,
STAY_Z = 2.0  # and a dozing light stays dozing while they bunch this much,
DOZE_MEDIAN_MS = 50.0  # either way only with a median round trip at least this long


@dataclass(frozen=True, slots=True)
class DozeReading:
    """What the check works out over the round trips it holds."""

    z: float  # the Rayleigh statistic of their arrivals' phases in a beacon cycle
    median_ms: float  # their median
    replies: int  # how many there are


def rayleigh_z(arrivals: Sequence[float], cycle_s: float = BEACON_S) -> float:
    """The Rayleigh statistic n·R² of the arrivals' phases in a cycle of cycle_s, R being
    their mean resultant length: near 0 for phases spread evenly, n for phases all at one
    point. For random arrivals, the chance that z ≥ k is about e^(−k)."""
    if not arrivals:
        return 0.0
    cos_sum = sin_sum = 0.0
    for arrived in arrivals:
        angle = math.tau * ((arrived / cycle_s) % 1.0)
        cos_sum += math.cos(angle)
        sin_sum += math.sin(angle)
    return (cos_sum * cos_sum + sin_sum * sin_sum) / len(arrivals)


class DozeCheck:
    """Whether a light's Wi-Fi dozes, from its last KEPT round trips and when each landed.
    An awake light turns dozing when z reaches DOZE_Z, and a dozing light stays dozing
    while z is at least STAY_Z, either way only while the median round trip is at least
    DOZE_MEDIAN_MS. With fewer than MIN_REPLIES round trips, the light keeps its mode."""

    def __init__(self, *, dozing: bool = False) -> None:
        self._dozing = dozing
        self._kept: deque[tuple[float, float]] = deque(maxlen=KEPT)

    @property
    def dozing(self) -> bool:
        return self._dozing

    @property
    def round_trips(self) -> list[float]:
        """The round trips held, in ms, oldest first."""
        return [rtt for _, rtt in self._kept]

    def reading(self) -> DozeReading | None:
        """z and the median over the round trips held; None with fewer than MIN_REPLIES."""
        if len(self._kept) < MIN_REPLIES:
            return None
        z = rayleigh_z([arrived for arrived, _ in self._kept])
        return DozeReading(z, statistics.median(self.round_trips), len(self._kept))

    def add(self, arrived_s: float, rtt_ms: float) -> bool:
        """A round trip that landed at arrived_s, on the tracker's clock. True when it
        changed the light's mode."""
        self._kept.append((arrived_s, rtt_ms))
        reading = self.reading()
        if reading is None:
            return False
        bunched = reading.z >= (STAY_Z if self._dozing else DOZE_Z)
        dozing = bunched and reading.median_ms >= DOZE_MEDIAN_MS
        changed = dozing != self._dozing
        self._dozing = dozing
        return changed
