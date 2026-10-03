"""A layer's view of its zone's LEDs: its mask, mirror and transform (spec §5.3).

Layer modifiers change where a field is drawn, never the effect. The mask weighs each LED
by where it sits (a height band, a room, a sub-zone, or the reach of an anchor), with a
soft edge where the band or the reach ends. The mirror and the transform move the
positions the effect sees: an LED shows what the field has at its mirrored and
transformed place. A view depends only on the LEDs and the modifiers, so the runtime keeps
one per layer until either changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.field_tools import anchor_or_centre, distances, smoothstep
from dj_ledfx.home.geometry import points_in_polygon
from dj_ledfx.home.shapes import rotation_matrix
from dj_ledfx.looks.model import (
    AnchorMask,
    HeightMask,
    Layer,
    Mask,
    Mirror,
    RoomMask,
    SubZoneMask,
    Transform,
)

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from dj_ledfx.effects.ledset import LedSet

MASK_EDGE_M = 0.1  # a height band's or an anchor's reach fades out over this many metres
_AXIS = {"x": 0, "y": 1, "z": 2}


@dataclass(frozen=True, eq=False)
class LayerView:
    """What a layer draws on: the LEDs its effect renders (the zone's own, or moved) and
    each LED's share of the layer, shape (N, 1); None: every LED in full."""

    leds: LedSet
    weight: NDArray[np.float32] | None = None


def layer_view(layer: Layer, leds: LedSet) -> LayerView:
    weight = None if layer.mask is None else mask_weights(layer.mask, leds)[:, None]
    if layer.mirror is None and layer.transform is None:
        return LayerView(leds, weight)
    pos = leds.pos.astype(np.float64)
    if layer.mirror is not None:
        pos = mirrored(layer.mirror, pos, leds.centre)
    if layer.transform is not None:
        pos = transformed(layer.transform, pos, leds.centre)
    return LayerView(leds.moved(pos), weight)


def mask_weights(mask: Mask, leds: LedSet) -> NDArray[np.float32]:
    """Each LED's share of a masked layer, 0..1, from where the LED sits. A room or a
    sub-zone the map doesn't have (any more) shows the layer nowhere; an anchor it doesn't
    have is the zone's middle, as it is for the effects."""
    half = MASK_EDGE_M / 2.0
    match mask:
        case HeightMask(low, high):
            z = leds.pos[:, 2]
            inside = smoothstep(low - half, low + half, z) * (
                1.0 - smoothstep(high - half, high + half, z)
            )
            weights: NDArray[np.float32] = inside.astype(np.float32)
            return weights
        case AnchorMask(anchor, radius):
            reach = distances(leds, anchor_or_centre(leds, anchor))
            near: NDArray[np.float32] = (
                1.0 - smoothstep(radius - half, radius + half, reach)
            ).astype(np.float32)
            return near
        case RoomMask(room):
            outline = leds.space.room_outlines.get(room)
        case SubZoneMask(sub_zone):
            outline = leds.space.sub_zone_outlines.get(sub_zone)
    if not outline:
        return np.zeros(leds.count, dtype=np.float32)
    inside_outline = points_in_polygon(leds.pos[:, :2].astype(np.float64), outline)
    return inside_outline.astype(np.float32)


def mirrored(
    mirror: Mirror, pos: NDArray[np.float64], centre: NDArray[np.float32]
) -> NDArray[np.float64]:
    """Positions folded across the mirror's plane: an LED on the high side sees the field
    at its reflection, so the low side shows on both."""
    axis = _AXIS[mirror.axis]
    at = float(centre[axis]) if mirror.at is None else mirror.at
    folded = pos.copy()
    high = folded[:, axis] > at
    folded[high, axis] = 2.0 * at - folded[high, axis]
    return folded


def transformed(
    transform: Transform, pos: NDArray[np.float64], centre: NDArray[np.float32]
) -> NDArray[np.float64]:
    """Where in the field each LED looks once the field is moved: shifted by the offset,
    turned clockwise seen from above (x east, y south) and grown by the scale, both about
    the zone's centre. An LED shows what the unmoved field has at the returned place."""
    middle = centre.astype(np.float64)
    back = (pos - np.asarray(transform.offset, dtype=np.float64) - middle) / transform.scale
    turn = rotation_matrix((transform.rotate_deg, 0.0, 0.0))  # the map's turn
    placed: NDArray[np.float64] = back @ turn + middle  # rows times it: turned back
    return placed
