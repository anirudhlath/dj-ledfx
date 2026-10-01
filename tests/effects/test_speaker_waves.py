from __future__ import annotations

import numpy as np
from conftest import tempo_ctx
from map_home import leds_at

from dj_ledfx.effects.color import palette_float
from dj_ledfx.effects.speaker_waves import SpeakerWaves

# Two speakers 4 m apart, and LEDs 1, 2 and 3 m along the line between them.
PAIR = {"speakers": [(0.0, 0.0, 1.0), (4.0, 0.0, 1.0)]}
BETWEEN = [(1.0, 0.0, 1.0), (2.0, 0.0, 1.0), (3.0, 0.0, 1.0)]
KICK, SNARE, REST = palette_float(["#ff5a1f", "#ffd23f", "#05030a"]) * 0.9


def test_kicks_send_a_wavefront_out_from_each_speaker() -> None:
    effect = SpeakerWaves(anchor="speakers", speed_m=6.0)
    leds = leds_at(BETWEEN, anchor_points=PAIR)

    # 120 BPM: a third of a beat is 1/6 s, so each front is 1 m out.
    frame = effect.render(tempo_ctx(4.0 + 1 / 3), leds)

    near_kick = np.linalg.norm(frame - KICK, axis=1)
    assert near_kick[0] < near_kick[1] and near_kick[2] < near_kick[1]
    assert np.allclose(frame[0], frame[2])  # one front from each speaker


def test_snares_bloom_between_the_speakers_on_the_second_and_fourth_beats() -> None:
    effect = SpeakerWaves(anchor="speakers")
    leds = leds_at(BETWEEN, anchor_points=PAIR)

    first, second = (effect.render(tempo_ctx(beats), leds) for beats in (4.0, 5.0))

    assert np.allclose(first[1], REST, atol=1e-3)
    assert np.allclose(second[1], SNARE, atol=1e-3)


def test_hats_sparkle_up_high_on_the_off_beat() -> None:
    effect = SpeakerWaves(anchor="speakers", sparkle=0.5)
    effect.reseed(3)
    low = [(float(x), 9.0, 0.3) for x in range(40)]
    high = [(float(x), 9.0, 2.9) for x in range(40)]
    leds = leds_at(low + high, ceiling=3.0, anchor_points={"speakers": [(80.0, 0.0, 1.0)]})

    on_the_beat = effect.render(tempo_ctx(4.25), leds)
    off_beat = effect.render(tempo_ctx(4.6), leds)
    next_off_beat = effect.render(tempo_ctx(5.6), leds)

    def sparkling(frame: np.ndarray) -> set[int]:
        return {i for i in range(80) if not np.allclose(frame[i], REST, atol=1e-3)}

    assert sparkling(on_the_beat) == set()
    assert sparkling(off_beat) and sparkling(off_beat) <= set(range(40, 80))  # high only
    assert sparkling(next_off_beat) != sparkling(off_beat)  # other LEDs each beat
