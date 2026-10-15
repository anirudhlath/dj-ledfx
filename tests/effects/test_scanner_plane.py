from __future__ import annotations

import numpy as np
from conftest import tempo_ctx
from map_home import leds_at

from dj_ledfx.effects.scanner_plane import ScannerPlane

FLOOR_TO_CEILING = [(0.0, 0.0, metres) for metres in (0.0, 0.75, 1.5, 2.25, 3.0)]


def test_the_plane_sweeps_up_and_back_every_two_beats() -> None:
    effect = ScannerPlane()
    leds = leds_at(FLOOR_TO_CEILING, ceiling=3.0)

    lit = [
        int(effect.render(tempo_ctx(beats), leds).sum(axis=1).argmax())
        for beats in (0.0, 0.5, 1.0, 1.5, 2.0)
    ]

    assert lit == [0, 2, 4, 2, 0]


# M8: the plane in space is level at the height it lights, in its colour, as thick as its
# band; with no map, between the zone's lowest and highest LEDs.
def test_the_plane_is_drawn_level_at_the_height_it_lights() -> None:
    effect = ScannerPlane(width=0.12)
    raised = [(x, y, z + 1.0) for x, y, z in FLOOR_TO_CEILING]  # 1 m to 4 m up
    for points, ceiling, low, high in (
        (FLOOR_TO_CEILING, 3.0, 0.0, 3.0),
        (raised, None, 1.0, 4.0),
    ):
        leds = leds_at(points, ceiling=ceiling)
        ctx = tempo_ctx(0.5)  # half-way up

        frame = effect.render(ctx, leds)
        fx = effect.in_space(ctx, leds)

        [point], [normal], [width] = fx.planes.point, fx.planes.normal, fx.planes.width
        assert np.isclose(point[2], (low + high) / 2) and normal.tolist() == [0.0, 0.0, 1.0]
        assert np.isclose(width, 2 * 0.12 * (high - low)) and not fx.planes.ray.any()
        assert np.allclose(fx.planes.colour[0], frame[2])  # the middle LED is lit full
