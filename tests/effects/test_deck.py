import pytest

from dj_ledfx.effects.beat_pulse import BeatPulse
from dj_ledfx.effects.deck import EffectDeck


def test_on_change_callback_fires_on_swap():
    calls = []
    deck = EffectDeck(BeatPulse(), on_change=lambda d: calls.append(d.effect_name))
    deck.apply_update("beat_pulse", {"gamma": 3.0})
    assert len(calls) == 1


def test_on_change_callback_fires_on_param_update():
    calls = []
    deck = EffectDeck(BeatPulse(), on_change=lambda d: calls.append("changed"))
    deck.apply_update(None, {"gamma": 5.0})
    assert len(calls) == 1


def test_no_callback_no_error():
    deck = EffectDeck(BeatPulse())
    deck.apply_update(None, {"gamma": 5.0})  # should not raise


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


class TestApplyUpdate:
    def test_swap_to_different_effect(self):
        deck = EffectDeck(BeatPulse(gamma=2.0))
        deck.apply_update("beat_pulse", {"gamma": 5.0})
        assert deck.effect.get_params()["gamma"] == 5.0

    def test_update_params_same_effect(self):
        deck = EffectDeck(BeatPulse(gamma=2.0))
        deck.apply_update("beat_pulse", {"gamma": 3.0})
        # effect_name matches current, so params are updated in-place
        assert deck.effect.get_params()["gamma"] == 3.0

    def test_noop_when_both_empty(self):
        deck = EffectDeck(BeatPulse(gamma=2.0))
        deck.apply_update(None, {})
        assert deck.effect_name == "beat_pulse"
        assert deck.effect.get_params()["gamma"] == 2.0

    def test_unknown_effect_raises_key_error(self):
        deck = EffectDeck(BeatPulse())
        with pytest.raises(KeyError):
            deck.apply_update("nonexistent_effect", {})
