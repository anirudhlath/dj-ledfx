from __future__ import annotations

import numpy as np
from conftest import tempo_ctx
from map_home import leds_at, seeded_ledset

from dj_ledfx.effects.checker_cubes import CheckerCubes

# Four 1 m cubes in a row of neighbours: across, across again, then up.
CUBES = [(0.5, 0.5, 0.5), (1.5, 0.5, 0.5), (1.5, 1.5, 0.5), (1.5, 1.5, 1.5)]
RED, BLUE = np.array([0.9, 0.0, 0.0]), np.array([0.0, 0.0, 0.9])


def test_neighbouring_cubes_swap_colours_on_each_beat() -> None:
    effect = CheckerCubes(palette=["#ff0000", "#0000ff"], punch=0.0)
    leds = leds_at(CUBES)

    first = effect.render(tempo_ctx(4.0), leds)
    second = effect.render(tempo_ctx(5.0), leds)

    assert np.allclose(first, [RED, BLUE, RED, BLUE])
    assert np.allclose(second, [BLUE, RED, BLUE, RED])


def test_each_beat_flashes_then_falls_by_the_punch() -> None:
    effect = CheckerCubes(palette=["#ff0000", "#0000ff"], punch=0.4)
    leds = leds_at(CUBES[:1])

    on_the_beat = effect.render(tempo_ctx(4.0), leds)
    halfway = effect.render(tempo_ctx(4.5), leds)

    assert np.allclose(on_the_beat[0], RED)
    assert np.allclose(halfway[0], RED * 0.8)


def test_frame_after_frame_it_draws_what_a_new_one_draws() -> None:
    """The colourings it keeps for the LEDs never change a frame, across beats and a new
    palette."""
    leds = seeded_ledset()
    effect = CheckerCubes()

    for k in range(6 * 30):  # six beats at 30 frames a beat
        palette = ["#ff2d95", "#21d4fd"] if k < 90 else ["#ff0000", "#00ff00", "#0000ff"]
        if k == 90:
            effect.set_params(palette=palette)
        ctx = tempo_ctx(4.0 + k / 30)
        assert np.array_equal(
            effect.render(ctx, leds), CheckerCubes(palette=palette).render(ctx, leds)
        ), k
