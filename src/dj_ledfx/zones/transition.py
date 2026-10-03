"""How a zone moves from one look to the next (engine spec §5.3).

Each LED goes from the old look's colour to the new look's as the transition's progress
passes its place in the switch order, over a soft edge: a wipe sweeps a plane across the
zone, a spread grows outward from an anchor, and a dissolve gives each LED its own random
moment. A fade moves every LED together, and a cut has no transition at all. The runtime
mixes the two looks' frames with these shares (runtime.py).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.field_tools import distances, smoothstep

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.looks.model import TransitionKind

# How much of the transition an LED's own change takes: a soft edge, not a hard line.
EDGES: dict[str, float] = {"wipe": 0.25, "spread": 0.25, "dissolve": 0.1}


def switch_order(kind: TransitionKind, leds: LedSet, seed: int) -> NDArray[np.float64] | None:
    """Each LED's place in the switch, 0 (first) to 1 (last), in the float64 new_share works
    in. A wipe runs along the zone's longer side on the floor, west to east or north to
    south; a spread runs outward from the anchor nearest the zone's middle (the middle
    itself on a map without anchors); a dissolve's places are random, the same for the same
    seed. None: every LED together (a fade or a cut)."""
    if leds.count == 0 or kind not in EDGES:
        return None
    if kind == "wipe":
        low, high = leds.bounds
        axis = 0 if high[0] - low[0] >= high[1] - low[1] else 1  # x east, y south
        along: NDArray[np.float64] = leds.npos[:, axis].astype(np.float64)
        return along
    if kind == "spread":
        reach = distances(leds, _nearest_anchor(leds))
        farthest = float(reach.max())
        spread = reach / np.float32(farthest) if farthest > 1e-6 else np.zeros_like(reach)
        return spread.astype(np.float64)
    order = np.random.default_rng(seed).random(leds.count, np.float32)
    return order.astype(np.float64)


def _nearest_anchor(leds: LedSet) -> NDArray[np.float32]:
    middle = leds.centre
    points = [np.asarray(point, dtype=np.float32) for point in leds.anchors.values()]
    if not points:
        return middle
    return min(points, key=lambda point: float(np.linalg.norm(point - middle)))


def new_share(
    kind: TransitionKind, order: NDArray[np.float64] | None, progress: float
) -> float | NDArray[np.float32]:
    """How much of the new look each LED shows at `progress` (0..1), shape (count, 1): an
    LED changes over the kind's edge, from where its place in the order meets the sweep. A
    fade's is one share for every LED."""
    if order is None:
        return smoothstep(0.0, 1.0, progress)
    edge = EDGES[kind]
    swept = progress * (1.0 + edge) - order  # how far the sweep is past each LED
    share: NDArray[np.float32] = smoothstep(0.0, edge, swept)[:, None]
    return share
