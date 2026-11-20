"""An overlay: a Home look played over every running zone for a set time (engine spec §4.3;
M6 rulings 10-14). The zone manager owns one at a time, in a slot the routes and the frame
feed share (scheduling/route.py's OverSource); the mix itself is route.overlaid()."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from dj_ledfx.effects.field_tools import smoothstep

if TYPE_CHECKING:
    from dj_ledfx.looks.model import Look
    from dj_ledfx.types import FloatRGB
    from dj_ledfx.zones.runtime import ZoneRuntime

MAX_OVERLAY_S = 3600.0
OVERLAY_EDGE_S = 0.25  # it eases in over this long, and out over the last of this long


@dataclass(frozen=True, slots=True)
class OverlayRun:
    """One overlay: its look, what started it, the runtime that renders it, and its span on
    the monotonic clock (`started_t`, `ends_t`) and on the wall clock (`started_at`,
    `ends_at`)."""

    look: Look
    trigger: str
    runtime: ZoneRuntime
    started_t: float
    ends_t: float
    started_at: datetime
    ends_at: datetime

    def amount(self, t: float) -> float:
        """How much of the overlay shows at t: 0 outside it, easing up over the first
        OVERLAY_EDGE_S and down over the last (a shorter one peaks below 1)."""
        if t <= self.started_t or t >= self.ends_t:
            return 0.0
        rising = smoothstep(self.started_t, self.started_t + OVERLAY_EDGE_S, t)
        falling = smoothstep(self.ends_t, self.ends_t - OVERLAY_EDGE_S, t)
        return float(min(rising, falling))


class OverlaySlot:
    """The overlay playing, or none, as what a route and the frame feed read (OverSource).
    `reaches` says whether the overlay reaches a light: not one its look has switched off."""

    def __init__(self, reaches: Callable[[str], bool]) -> None:
        self.run: OverlayRun | None = None
        self._reaches = reaches

    def over_at(self, device_id: str, t: float, count: int) -> tuple[FloatRGB, float] | None:
        """The overlay's colours for the light at t and their amount, or None: nothing
        plays, it doesn't reach the light, its slice isn't `count` LEDs, its ring is empty
        or the amount is 0. Nothing is copied: the colours are the ring's own."""
        run = self.run
        if run is None or not self._reaches(device_id):
            return None
        amount = run.amount(t)
        if amount <= 0.0:
            return None
        piece = run.runtime.leds.slice_for(device_id)
        if piece is None or piece.count != count:
            return None
        colors = run.runtime.ring.colors_at(t, piece.start, piece.stop)
        return None if colors is None else (colors, amount)
