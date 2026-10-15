"""A layer's view of its zone's LEDs: its mask, mirror and transform (spec §5.3).

Layer modifiers change where a field is drawn, never the effect. The mask weighs each LED
by where it sits (a height band, a room, a sub-zone, or the reach of an anchor), with a
soft edge where the band or the reach ends. The mirror and the transform move the
positions the effect sees: an LED shows what the field has at its mirrored and
transformed place. A view depends only on the LEDs and the modifiers, so the runtime keeps
one per layer until either changes.

What the layer's effect draws in space (effects/fx.py) is in the effect's own space; the
view maps it back onto the map (in_home()), where the stage draws it.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.field_tools import anchor_or_centre, smoothstep
from dj_ledfx.effects.fx import NO_PLANES, NO_RINGS, Fx, Planes, Rings
from dj_ledfx.effects.particle_tools import Particles
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
    each LED's share of the layer, shape (N, 1); None: every LED in full. `zone` is the
    zone's own LED set, where the mask and the moves were made (None: `leds`, unmoved)."""

    leds: LedSet
    weight: NDArray[np.float32] | None = None
    zone: LedSet | None = None
    mask: Mask | None = None
    mirror: Mirror | None = None
    transform: Transform | None = None

    @cached_property
    def among(self) -> NDArray[np.bool_] | None:
        """The LEDs the mask weighs above 0 (None: no mask, every LED): a particle layer's
        lamps are made of these, one array for as long as the view is kept."""
        return None if self.weight is None else self.weight[:, 0] > 0.0

    def in_home(self, fx: Fx) -> Fx:
        """What the layer's effect draws, moved from the effect's space onto the map: back
        through the transform, then at every place the mirror shows it. A particle the
        mirror doesn't show (past its plane) is left out, and one in both halves is drawn
        in both; a ring or a plane is drawn whole at its place and at its reflection. The
        mask weighs each particle's colour where it lands, and one it weighs 0 is left out;
        a ring or a plane is drawn whole while the mask weighs any LED, else not at all."""
        zone = self.zone or self.leds
        centre = zone.centre.astype(np.float64)
        particles, rings, planes = fx.particles, fx.rings, fx.planes
        if self.transform is not None:
            particles, rings, planes = _unmoved(self.transform, centre, particles, rings, planes)
        if self.mirror is not None:
            axis = _AXIS[self.mirror.axis]
            at = float(centre[axis]) if self.mirror.at is None else self.mirror.at
            particles = _particle_images(particles, axis, at)
            rings, planes = _ring_images(rings, axis, at), _plane_images(planes, axis, at)
        if self.mask is not None:
            particles = _weighed(particles, mask_weights_at(self.mask, particles.pos, zone))
            if not bool(self.among is not None and self.among.any()):
                rings, planes = NO_RINGS, NO_PLANES
        return Fx(particles, rings, planes)


def layer_view(layer: Layer, leds: LedSet) -> LayerView:
    weight = None if layer.mask is None else mask_weights(layer.mask, leds)[:, None]
    if layer.mirror is None and layer.transform is None:
        return LayerView(leds, weight, mask=layer.mask)
    pos = leds.pos.astype(np.float64)
    if layer.mirror is not None:
        pos = mirrored(layer.mirror, pos, leds.centre)
    if layer.transform is not None:
        pos = transformed(layer.transform, pos, leds.centre)
    return LayerView(leds.moved(pos), weight, leds, layer.mask, layer.mirror, layer.transform)


def mask_weights(mask: Mask, leds: LedSet) -> NDArray[np.float32]:
    """Each LED's share of a masked layer, 0..1, from where the LED sits. A room or a
    sub-zone the map doesn't have (any more) shows the layer nowhere; an anchor it doesn't
    have is the zone's middle, as it is for the effects."""
    return mask_weights_at(mask, leds.pos, leds)


def mask_weights_at(mask: Mask, pos: NDArray[np.float32], leds: LedSet) -> NDArray[np.float32]:
    """The mask's weight, 0..1, at each of these places on the map (an LED's, or a
    particle's), in the zone of these LEDs: its rooms', sub-zones' and anchors' places."""
    half = MASK_EDGE_M / 2.0
    match mask:
        case HeightMask(low, high):
            z = pos[:, 2]
            inside = smoothstep(low - half, low + half, z) * (
                1.0 - smoothstep(high - half, high + half, z)
            )
            weights: NDArray[np.float32] = inside.astype(np.float32)
            return weights
        case AnchorMask(anchor, radius):
            point = anchor_or_centre(leds, anchor)
            reach = np.asarray(np.linalg.norm(pos - point, axis=1), dtype=np.float32)
            near: NDArray[np.float32] = (
                1.0 - smoothstep(radius - half, radius + half, reach)
            ).astype(np.float32)
            return near
        case RoomMask(room):
            outline = leds.space.room_outlines.get(room)
        case SubZoneMask(sub_zone):
            outline = leds.space.sub_zone_outlines.get(sub_zone)
    if not outline:
        return np.zeros(len(pos), dtype=np.float32)
    inside_outline = points_in_polygon(pos[:, :2].astype(np.float64), outline)
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


def _unmoved(
    transform: Transform,
    centre: NDArray[np.float64],
    particles: Particles,
    rings: Rings,
    planes: Planes,
) -> tuple[Particles, Rings, Planes]:
    """Things in the effect's space where the transform shows them on the map: transformed()
    undone. Places go back through the turn, the scale and the offset; directions through
    the turn alone; lengths grow by the scale."""
    turn = rotation_matrix((transform.rotate_deg, 0.0, 0.0))
    offset = np.asarray(transform.offset, dtype=np.float64)
    scale = transform.scale

    def place(points: NDArray[np.float32]) -> NDArray[np.float32]:
        back = ((points.astype(np.float64) - centre) @ turn.T) * scale + centre + offset
        return back.astype(np.float32)

    def turned(directions: NDArray[np.float32]) -> NDArray[np.float32]:
        return (directions.astype(np.float64) @ turn.T).astype(np.float32)

    grown = np.float32(scale)
    return (
        Particles(place(particles.pos), particles.colour, particles.radius * grown),
        Rings(
            place(rings.centre),
            rings.radius * grown,
            rings.width * grown,
            rings.colour,
            rings.circle,
        ),
        Planes(
            place(planes.point),
            turned(planes.normal),
            planes.width * grown,
            planes.colour,
            turned(planes.ray),
        ),
    )


def _reflected(points: NDArray[np.float32], axis: int, at: float) -> NDArray[np.float32]:
    across = points.copy()
    across[:, axis] = 2.0 * at - across[:, axis]
    return across


def _flipped(directions: NDArray[np.float32], axis: int) -> NDArray[np.float32]:
    across = directions.copy()
    across[:, axis] = -across[:, axis]
    return across


def _particle_images(particles: Particles, axis: int, at: float) -> Particles:
    """The particles the mirror shows, each at its place and then at its reflection, so the
    two stay side by side, oldest first: those on its low side, since an LED on the high
    side sees the field at its own reflection."""
    shown = particles.pick(particles.pos[:, axis] <= at)

    def twice(values: NDArray[np.float32]) -> NDArray[np.float32]:
        return np.repeat(values, 2, axis=0)

    pos = twice(shown.pos)
    pos[1::2] = _reflected(shown.pos, axis, at)
    return Particles(pos, twice(shown.colour), twice(shown.radius))


def _ring_images(rings: Rings, axis: int, at: float) -> Rings:
    return Rings(
        np.concatenate([rings.centre, _reflected(rings.centre, axis, at)]),
        np.concatenate([rings.radius, rings.radius]),
        np.concatenate([rings.width, rings.width]),
        np.concatenate([rings.colour, rings.colour]),
        np.concatenate([rings.circle, rings.circle]),
    )


def _plane_images(planes: Planes, axis: int, at: float) -> Planes:
    return Planes(
        np.concatenate([planes.point, _reflected(planes.point, axis, at)]),
        np.concatenate([planes.normal, _flipped(planes.normal, axis)]),
        np.concatenate([planes.width, planes.width]),
        np.concatenate([planes.colour, planes.colour]),
        np.concatenate([planes.ray, _flipped(planes.ray, axis)]),
    )


def _weighed(particles: Particles, weights: NDArray[np.float32]) -> Particles:
    """Each particle's colour times its weight, leaving out those weighed 0."""
    kept = weights > 0.0
    shown = particles.pick(kept)
    return Particles(shown.pos, shown.colour * weights[kept][:, None], shown.radius)
