from __future__ import annotations

import numpy as np
from conftest import tempo_ctx
from map_home import leds_at

from dj_ledfx.effects.shockwave_shell import ShockwaveShell

FROM_THE_TV = [(float(metres), 0.0, 1.0) for metres in range(7)]  # 0 to 6 m away
TV = {"tv": (0.0, 0.0, 1.0)}


def test_the_shell_leaves_the_anchor_on_the_beat_and_fades_as_it_spreads() -> None:
    effect = ShockwaveShell(anchor="tv", reach_m=6.0)
    leds = leds_at(FROM_THE_TV, anchors=TV)

    on_the_beat = effect.render(tempo_ctx(8.0), leds).sum(axis=1)
    a_third_on = effect.render(tempo_ctx(8.0 + 1 / 3), leds).sum(axis=1)

    assert on_the_beat.argmax() == 0  # at the TV
    assert a_third_on.argmax() == 2  # 6 m a beat: 2 m a third of a beat on
    assert a_third_on.max() < on_the_beat.max()  # dimmer as it spreads


def test_without_its_anchor_the_shell_starts_in_the_middle() -> None:
    leds = leds_at([(0.0, 0.0, 1.0), (3.0, 0.0, 1.0), (6.0, 0.0, 1.0)])

    frame = ShockwaveShell(anchor="gone").render(tempo_ctx(4.0), leds)

    assert frame.sum(axis=1).argmax() == 1


# M8: the shell in space is where it lights the LEDs, in the colour its crest lights them.
def test_the_shell_is_drawn_as_a_sphere_round_the_anchor_out_to_its_front() -> None:
    effect = ShockwaveShell(anchor="tv", reach_m=6.0, shell_m=0.6)
    leds = leds_at(FROM_THE_TV, anchors=TV)
    ctx = tempo_ctx(8.0 + 1 / 3)

    frame = effect.render(ctx, leds)
    fx = effect.in_space(ctx, leds)

    assert fx.particles.count == 0 and fx.planes.count == 0
    [centre], [radius], [width] = fx.rings.centre, fx.rings.radius, fx.rings.width
    assert np.allclose(centre, TV["tv"]) and not fx.rings.circle[0]  # a sphere's shell
    assert np.isclose(radius, 2.0) and np.isclose(width, 1.2)  # 6 m a beat; twice 0.6 m
    assert np.allclose(fx.rings.colour[0], frame[2])  # the LED 2 m out is on the crest
