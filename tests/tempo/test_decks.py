from __future__ import annotations

from tempo_fakes import PLAYER, beat_event

from dj_ledfx.tempo.decks import DeckTracker
from dj_ledfx.tempo.model import SET_GAP_S, DeckView


def test_a_deck_plays_while_its_beats_arrive_and_is_cued_after() -> None:
    decks = DeckTracker()
    decks.hear(beat_event(10.0, deck=2, bpm=124.0, pitch_percent=1.2))

    assert decks.views(11.9, master=2) == (DeckView(2, PLAYER, "playing", 124.0, 1.2, True),)
    assert decks.any_playing(11.9)
    assert decks.views(12.1, master=None) == (DeckView(2, PLAYER, "cued", 124.0, 1.2, False),)
    assert not decks.any_playing(12.1)


def test_the_first_deck_is_followed_until_it_goes_quiet() -> None:
    decks = DeckTracker()

    decks.hear(beat_event(10.0, deck=1))  # the first deck heard
    assert decks.followed == 1
    decks.hear(beat_event(10.2, deck=2))  # a second deck in the mix
    decks.hear(beat_event(10.47, deck=1))
    assert decks.followed == 1
    decks.hear(beat_event(12.6, deck=2))  # deck 1 quiet for over 2 s
    assert decks.followed == 2


def test_a_deck_shows_its_track_bpm_and_pitch_apart() -> None:
    decks = DeckTracker()
    decks.hear(beat_event(10.0, deck=1, bpm=124.0, pitch_percent=1.2))

    [one] = decks.views(10.0, master=None)

    assert (one.bpm, one.pitch_percent) == (124.0, 1.2)


def test_decks_are_forgotten_once_a_set_is_over() -> None:
    decks = DeckTracker()
    decks.hear(beat_event(10.0, deck=1))

    decks.forget(10.0 + SET_GAP_S)
    assert decks.followed == 1
    decks.forget(10.0 + SET_GAP_S + 1.0)

    assert decks.views(10.0 + SET_GAP_S + 1.0, master=None) == ()
    assert decks.followed is None
