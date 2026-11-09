"""The `fx` channel's message (web spec §12.4, "The `fx` payload"): what each zone draws in
space now, in the home map's frame, for the stage's "Effects in space".

Colours are the frame's times the zone's brightness, clipped to 0..1, and every number is
rounded to 3 decimals. An item whose colour rounds to black, or that holds a number JSON
can't carry, is left out, and so is a zone left with nothing. Past MAX_FX_PARTICLES a zone
keeps its newest particles, as a particle effect's step keeps its own.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from dj_ledfx.zones.frames import ZoneFx

FX_FPS = 30.0  # at most this many fx messages a second, to each session
# A zone's particles in one message, for each stream: the effects' own cap (MAX_PARTICLES),
# so a particle layer is never cut unless a mirror doubles it or layers add up. A full zone
# is about 25 KB of JSON and takes under a millisecond to encode; this home's particle looks
# make at most 76 at their defaults and 380 at their largest settings.
MAX_FX_PARTICLES = 500
DECIMALS = 3
_RGB = slice(3, 6)  # every table below has its colour in columns 3 to 5


def fx_message(shown: Sequence[ZoneFx]) -> dict[str, Any]:
    """The whole picture, one entry for each zone that draws anything: it replaces the last."""
    zones = [zone for zone in (_zone(each) for each in shown) if zone is not None]
    return {"channel": "fx", "zones": zones}


def _zone(shown: ZoneFx) -> dict[str, Any] | None:
    fx, scale = shown.fx, shown.brightness
    out: dict[str, Any] = {"zoneId": shown.zone_id, "stream": shown.stream}
    particles = fx.particles.newest(MAX_FX_PARTICLES)
    rows, _ = _table(particles.pos, _lit(particles.colour, scale), particles.radius)
    if len(rows):
        out["particles"] = rows.tolist()  # x, y, z, r, g, b, size
    rings = fx.rings
    rows, kept = _table(rings.centre, _lit(rings.colour, scale), rings.radius, rings.width)
    if len(rows):
        out["rings"] = [
            {
                "center": row[0:3],
                "radius": row[6],
                "width": row[7],
                "rgb": row[_RGB],
                "form": "circle" if circle else "sphere",
            }
            for row, circle in zip(rows.tolist(), rings.circle[kept].tolist(), strict=True)
        ]
    planes = fx.planes
    rows, _ = _table(
        planes.point, _lit(planes.colour, scale), planes.normal, planes.width, planes.ray
    )
    if len(rows):
        out["planes"] = [_plane(row) for row in rows.tolist()]
    return out if len(out) > 2 else None


def _plane(row: list[float]) -> dict[str, Any]:
    plane: dict[str, Any] = {
        "point": row[0:3],
        "normal": row[6:9],
        "width": row[9],
        "rgb": row[_RGB],
    }
    if any(row[10:13]):  # a ray: the half of the plane on its side of the point
        plane["ray"] = row[10:13]
    return plane


def _lit(colour: NDArray[np.float32], scale: float) -> NDArray[np.float64]:
    """Colours at the zone's brightness, 0..1."""
    return np.clip(colour.astype(np.float64) * scale, 0.0, 1.0)


def _table(*columns: NDArray[Any]) -> tuple[NDArray[np.float64], NDArray[np.bool_]]:
    """The columns side by side, a row for each item, rounded; the rows kept (finite, and
    not black once rounded), and which those were."""
    rows = np.round(np.concatenate([_column(c) for c in columns], 1), DECIMALS)
    kept = np.isfinite(rows).all(axis=1) & (rows[:, _RGB].max(axis=1, initial=0.0) > 0.0)
    return rows[kept], kept


def _column(values: NDArray[Any]) -> NDArray[np.float64]:
    """Values as rows of a table, (K,) as (K, 1): none at all still has its width."""
    width = int(np.prod(values.shape[1:]))
    return np.asarray(values, dtype=np.float64).reshape(len(values), width)
