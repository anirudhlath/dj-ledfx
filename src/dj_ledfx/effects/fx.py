"""What an effect draws in space (engine spec §4.1: "From M8, effects can also describe what
they draw in space"), for the web app's stage (web spec §7.4, and §12.4's `fx` payload).

An effect says it through one hook, `Effect.in_space(ctx, leds)`, None by default: a
particle effect's are its particles, and the field effects that draw a shell, a front, a
ripple or a plane say where it is. Positions and lengths are metres on the map's axes as
the effect sees them (a layer's view moves them; `LayerView.in_home()` maps them back),
colours linear 0..1 as the effect draws them, before the layer's opacity, the look's
modifiers and the zone's brightness.

`width` is how thick a ring or a plane is drawn: its light's full width where it falls to
e^-1, twice the `band()` width its effect lights the LEDs with.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from dj_ledfx.effects.particle_tools import NO_PARTICLES, Particles, joined

F32 = NDArray[np.float32]
Recolour = Callable[[F32], F32]  # (K, 3) colours to (K, 3) colours, in an array of its own


def _rows(values: ArrayLike, count: int, width: int) -> F32:
    """One row of `width` floats for each of `count` items: given for each, or one for all."""
    shape = (count, width) if width > 1 else (count,)
    return np.broadcast_to(np.asarray(values, dtype=np.float32), shape).astype(np.float32)


@dataclass(frozen=True, eq=False, slots=True)
class Rings:
    """Shells and level rings of light: each one's centre, radius, width and colour, and
    whether it's a level circle (its axis z) rather than a sphere's shell."""

    centre: F32  # (K, 3)
    radius: F32  # (K,)
    width: F32  # (K,)
    colour: F32  # (K, 3)
    circle: NDArray[np.bool_]  # (K,)

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
        where,
        _rows(radius, count, 1),
        _rows(width, count, 1),
        _rows(colour, count, 3),
        np.full(count, circle, dtype=np.bool_),
    )


@dataclass(frozen=True, eq=False, slots=True)
class Planes:
    """Planes of light: a point on each, its unit normal, width and colour, and its ray, a
    direction in the plane: the plane is the half on that side of the point (a beam). A ray
    of zeros: the whole plane."""

    point: F32  # (K, 3)
    normal: F32  # (K, 3)
    width: F32  # (K,)
    colour: F32  # (K, 3)
    ray: F32  # (K, 3)

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
    ray."""
    where = np.array(point, dtype=np.float32).reshape(-1, 3)
    count = len(where)
    return Planes(
        where,
        _rows(normal, count, 3),
        _rows(width, count, 1),
        _rows(colour, count, 3),
        _rows(ray, count, 3),
    )


NO_RINGS = rings(np.zeros((0, 3)), 0.0, 0.0, (0.0, 0.0, 0.0))
NO_PLANES = planes(np.zeros((0, 3)), (0.0, 0.0, 1.0), 0.0, (0.0, 0.0, 0.0))


@dataclass(frozen=True, eq=False, slots=True)
class Fx:
    """What one layer, or a zone's frame, draws in space."""

    particles: Particles = NO_PARTICLES
    rings: Rings = NO_RINGS
    planes: Planes = NO_PLANES

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
    """Several layers' fx as one, bottom layer first; None for none."""
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return Fx(
        joined(*(part.particles for part in parts)),
        Rings(
            *(
                np.concatenate([getattr(part.rings, name) for part in parts])
                for name in ("centre", "radius", "width", "colour", "circle")
            )
        ),
        Planes(
            *(
                np.concatenate([getattr(part.planes, name) for part in parts])
                for name in ("point", "normal", "width", "colour", "ray")
            )
        ),
    )
