from __future__ import annotations

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
