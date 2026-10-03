import numpy as np
from conftest import beat_ctx

from dj_ledfx.effects.color_chase import ColorChase

RED, GREEN, BLUE, WHITE = [255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 255]
FOUR = ["#ff0000", "#00ff00", "#0000ff", "#ffffff"]


def _first_light(chase: ColorChase, beats: float) -> list[int]:
    return chase.render(beat_ctx(beats), 5)[0].tolist()


def test_output_shape_and_dtype():
    effect = ColorChase()
    result = effect.render(beat_ctx(0.0), 20)
    assert result.shape == (20, 3)
    assert result.dtype == np.uint8


def test_spatial_gradient():
    effect = ColorChase()
    result = effect.render(beat_ctx(0.0), 20)
    # Not all LEDs should be the same color (spatial variation)
    assert not np.all(result == result[0])


def test_single_led_degradation():
    effect = ColorChase()
    result = effect.render(beat_ctx(0.0), 1)
    assert result.shape == (1, 3)
    assert result.max() > 0


def test_parameters_schema():
    schema = ColorChase.parameters()
    assert "palette" in schema
    assert "band_count" in schema
    assert "direction" in schema
    assert schema["direction"].type == "choice"
    assert schema["band_count"].label == "Band count"
    step = schema["beats_per_step"]
    # Half a beat at least: a light swings from dark to bright and back at most once a beat
    assert (step.type, step.default, step.min, step.max, step.step, step.label) == (
        "float",
        1.0,
        0.5,
        8.0,
        0.25,
        "Beats per step",
    )


def test_get_set_params():
    effect = ColorChase(band_count=3.0)
    assert effect.get_params()["band_count"] == 3.0
    effect.set_params(band_count=5.0)
    assert effect.get_params()["band_count"] == 5.0
    assert effect.get_params()["beats_per_step"] == 1.0
    effect.set_params(beats_per_step=2.0)
    assert effect.get_params()["beats_per_step"] == 2.0


def test_a_light_glides_one_colour_along_a_beat_and_round_the_palette() -> None:
    chase = ColorChase(palette=FOUR, band_count=1.0)
    beats = (0.0, 1.0, 2.0, 3.0, 4.0, 13.0)
    assert [_first_light(chase, b) for b in beats] == [RED, GREEN, BLUE, WHITE, RED, GREEN]
    assert _first_light(chase, 0.5) == [127, 127, 0]  # half-way from red to green
    assert _first_light(chase, 3.5) == [255, 127, 127]  # white glides back into red


def test_beats_per_step_sets_how_long_each_colour_takes() -> None:
    slow = ColorChase(palette=FOUR, band_count=1.0, beats_per_step=2.0)
    assert [_first_light(slow, b) for b in (0.0, 1.0, 2.0, 4.0)] == [
        RED,
        [127, 127, 0],
        GREEN,
        BLUE,
    ]
    fast = ColorChase(palette=FOUR, band_count=1.0, beats_per_step=0.5)
    assert [_first_light(fast, b) for b in (0.5, 1.0)] == [GREEN, BLUE]


# One band over five LEDs puts the palette's four colours a LED apart.
def test_the_colours_travel_forward_a_light_a_step() -> None:
    chase = ColorChase(palette=FOUR, band_count=1.0)
    before, after = chase.render(beat_ctx(6.0), 5), chase.render(beat_ctx(7.0), 5)
    assert np.array_equal(after[1:], before[:-1])


def test_reverse_sends_them_back_the_other_way() -> None:
    chase = ColorChase(palette=FOUR, band_count=1.0, direction="reverse")
    before, after = chase.render(beat_ctx(6.0), 5), chase.render(beat_ctx(7.0), 5)
    assert np.array_equal(after[:-1], before[1:])


def test_a_light_glides_on_over_beats_and_bars() -> None:
    chase = ColorChase(palette=FOUR[:3])  # three colours: not a bar
    for beat in (1.0, 4.0, 7.0):
        before = chase.render(beat_ctx(beat - 1e-6), 20).astype(int)
        on = chase.render(beat_ctx(beat), 20).astype(int)
        assert np.abs(on - before).max() <= 1


def test_the_tempo_sets_when_the_beats_come_and_nothing_else() -> None:
    chase = ColorChase()
    slow, fast = beat_ctx(2.5, bpm=90.0), beat_ctx(2.5, bpm=150.0)
    assert np.array_equal(chase.render(slow, 20), chase.render(fast, 20))


def test_new_settings_apply_from_the_next_frame() -> None:
    for settings in ({"direction": "reverse"}, {"band_count": 3.0}):
        chase = ColorChase(palette=FOUR)
        chase.render(beat_ctx(1.0), 20)
        chase.set_params(**settings)
        fresh = ColorChase(palette=FOUR, **settings)  # type: ignore[arg-type]
        assert np.array_equal(chase.render(beat_ctx(1.0), 20), fresh.render(beat_ctx(1.0), 20))
