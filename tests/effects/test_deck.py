from dj_ledfx.effects.beat_pulse import BeatPulse
from dj_ledfx.effects.deck import EffectDeck


def test_deck_delegates_render():
    effect = BeatPulse()
    deck = EffectDeck(effect)
    result = deck.render(0.5, 0.25, 0.016, 10)
    assert result.shape == (10, 3)


def test_deck_effect_name():
    deck = EffectDeck(BeatPulse())
    assert deck.effect_name == "beat_pulse"


def test_deck_swap_effect():
    deck = EffectDeck(BeatPulse(gamma=2.0))
    assert deck.effect.get_params()["gamma"] == 2.0
    deck.swap_effect(BeatPulse(gamma=4.0))
    assert deck.effect.get_params()["gamma"] == 4.0


def test_deck_render_after_swap():
    deck = EffectDeck(BeatPulse())
    deck.swap_effect(BeatPulse(gamma=1.0))
    result = deck.render(0.0, 0.0, 0.016, 5)
    assert result.shape == (5, 3)
