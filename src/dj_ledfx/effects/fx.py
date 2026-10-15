"""What an effect draws in space (engine spec §4.1: "From M8, effects can also describe what
they draw in space"), for the web app's stage (web spec §7.4, and §12.4's `fx` payload).

An effect says it through one hook, `Effect.in_space(ctx, leds)`, None by default: a
particle effect's are its particles, and the field effects that draw a shell, a front, a
ripple or a plane say where it is. Positions and lengths are metres on the map's axes as
the effect sees them (a layer's view moves them; `LayerView.in_home()` maps them back),
colours linear 0..1 as the effect draws them, before the layer's opacity, the look's
modifiers and the zone's brightness.

`width` is how thick a ring or a plane is drawn: its light's full width where it falls to
e^-1, twice the `band()` width its effect lights the LEDs with. The exception is a plane
with a `ray` (a beam), whose `width` is an angle in radians.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from dj_ledfx.effects.particle_tools import NO_PARTICLES, Particles, joined

F32 = NDArray[np.float32]
Recolour = Callable[[F32], F32]  # (K, 3) colours to (K, 3) colours, in an array of its own


def _rows(name: str, values: ArrayLike, count: int, width: int) -> F32:
    """One row of `width` floats for each of `count` items: given for each, or one for all.
    Any other shape raises a ValueError that names the value."""
    one = (width,) if width > 1 else ()
    array = np.asarray(values, dtype=np.float32)
    if array.shape not in (one, (count, *one)):
        raise ValueError(
            f"{name} takes one for all or one for each of the {count} items, "
            f"not an array of shape {array.shape}"
        )
    return np.broadcast_to(array, (count, *one)).astype(np.float32)


def _read_only(*arrays: NDArray[Any]) -> None:
    """Frozen in place: an Fx is never changed, so one shared (fx_joined of one) is safe."""
    for array in arrays:
        array.flags.writeable = False


@dataclass(frozen=True, eq=False, slots=True)
class Rings:
    """Shells and level rings of light: each one's centre, radius, width and colour, and
    whether it's a level circle (its axis z) rather than a sphere's shell. A ring's width is
    its light's full thickness where it falls to e^-1."""

    centre: F32  # (K, 3)
    radius: F32  # (K,)
    width: F32  # (K,)
    colour: F32  # (K, 3)
    circle: NDArray[np.bool_]  # (K,)

    def __post_init__(self) -> None:
        _read_only(self.centre, self.radius, self.width, self.colour, self.circle)

    @property
    def count(self) -> int:
        return int(self.centre.shape[0])


def rings(
    centre: ArrayLike,
    radius: ArrayLike,
    width: ArrayLike,
    colour: ArrayLike,
    *,
    circle: bool = False,
) -> Rings:
    """Rings from centres (K, 3) and each one's (or one for all) radius, width and colour."""
    where = np.array(centre, dtype=np.float32).reshape(-1, 3)
    count = len(where)
    return Rings(
        centre=where,
        radius=_rows("radius", radius, count, 1),
        width=_rows("width", width, count, 1),
        colour=_rows("colour", colour, count, 3),
        circle=np.full(count, circle, dtype=np.bool_),
    )


@dataclass(frozen=True, eq=False, slots=True)
class Planes:
    """Planes of light: a point on each, its unit normal, width and colour, and its ray, a
    direction in the plane: the plane is the half on that side of the point (a beam). A ray
    of zeros: the whole plane. A plane's width is its light's full thickness where it falls
    to e^-1, but a plane with a ray gives it as an angle in radians."""

    point: F32  # (K, 3)
    normal: F32  # (K, 3)
    width: F32  # (K,)
    colour: F32  # (K, 3)
    ray: F32  # (K, 3)

    def __post_init__(self) -> None:
        _read_only(self.point, self.normal, self.width, self.colour, self.ray)

    @property
    def count(self) -> int:
        return int(self.point.shape[0])


def planes(
    point: ArrayLike,
    normal: ArrayLike,
    width: ArrayLike,
    colour: ArrayLike,
    ray: ArrayLike = (0.0, 0.0, 0.0),
) -> Planes:
    """Planes from points (K, 3) and each one's (or one for all) normal, width, colour and
    ray; with a ray, the width is an angle in radians."""
    where = np.array(point, dtype=np.float32).reshape(-1, 3)
    count = len(where)
    return Planes(
        point=where,
        normal=_rows("normal", normal, count, 3),
        width=_rows("width", width, count, 1),
        colour=_rows("colour", colour, count, 3),
        ray=_rows("ray", ray, count, 3),
    )


NO_RINGS = rings(np.zeros((0, 3)), 0.0, 0.0, (0.0, 0.0, 0.0))
NO_PLANES = planes(np.zeros((0, 3)), (0.0, 0.0, 1.0), 0.0, (0.0, 0.0, 0.0))


@dataclass(frozen=True, eq=False, slots=True)
class Fx:
    """What one layer, or a zone's frame, draws in space. Its arrays are read-only, the
    particles' too (a particle effect's own last step's): every change makes a new Fx."""

    particles: Particles = NO_PARTICLES
    rings: Rings = NO_RINGS
    planes: Planes = NO_PLANES

    def __post_init__(self) -> None:
        particles = self.particles
        _read_only(particles.pos, particles.colour, particles.radius)

    @property
    def empty(self) -> bool:
        return self.particles.count == 0 and self.rings.count == 0 and self.planes.count == 0

    def recoloured(self, change: Recolour) -> Fx:
        """Every colour changed by `change` (a layer's opacity, the evening, the cap)."""
        particles, ring, plane = self.particles, self.rings, self.planes
        return Fx(
            Particles(particles.pos, change(particles.colour), particles.radius),
            Rings(ring.centre, ring.radius, ring.width, change(ring.colour), ring.circle),
            Planes(plane.point, plane.normal, plane.width, change(plane.colour), plane.ray),
        )


NO_FX = Fx()


def fx_joined(parts: list[Fx]) -> Fx | None:
    """Several layers' fx as one, bottom layer first; None for none. One alone is handed
    back as it is: its arrays are read-only, so sharing them is safe."""
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    ring_parts = [part.rings for part in parts]
    plane_parts = [part.planes for part in parts]
    return Fx(
        particles=joined(*(part.particles for part in parts)),
        rings=Rings(
            centre=np.concatenate([each.centre for each in ring_parts]),
            radius=np.concatenate([each.radius for each in ring_parts]),
            width=np.concatenate([each.width for each in ring_parts]),
            colour=np.concatenate([each.colour for each in ring_parts]),
            circle=np.concatenate([each.circle for each in ring_parts]),
        ),
        planes=Planes(
            point=np.concatenate([each.point for each in plane_parts]),
            normal=np.concatenate([each.normal for each in plane_parts]),
            width=np.concatenate([each.width for each in plane_parts]),
            colour=np.concatenate([each.colour for each in plane_parts]),
            ray=np.concatenate([each.ray for each in plane_parts]),
        ),
    )
