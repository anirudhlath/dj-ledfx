"""The players that Pro DJ Link's beat packets tell of (spec §7.2 and §11.7).

Passive mode hears beat packets only, so a deck is playing while its beats arrive and
cued once they stop; "empty" and the DJ's own tempo master need status packets, which
need a virtual CDJ. The clock follows one deck at a time: the first one heard, until it
goes quiet. So two decks in a mix never pull the beat back and forth.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from dj_ledfx.events import BeatEvent
from dj_ledfx.tempo.model import QUIET_S, SET_GAP_S, DeckView


@dataclass(slots=True)
class _Deck:
    number: int
    player: str
    track_bpm: float
    pitch_percent: float
    heard_at: float  # time.monotonic() of its last beat


class DeckTracker:
    def __init__(self) -> None:
        self._decks: dict[int, _Deck] = {}
        self.followed: int | None = None  # the deck the clock follows

    def hear(self, event: BeatEvent) -> bool:
        """Note a deck's beat. True when the clock follows a different deck from now."""
        track_bpm = event.track_bpm
        if not (math.isfinite(track_bpm) and track_bpm > 0):
            track_bpm = event.bpm  # an event that doesn't know its track's BPM
        self._decks[event.device_number] = _Deck(
            event.device_number,
            event.device_name,
            track_bpm,
            event.pitch_percent,
            event.timestamp,
        )
        followed = self._decks.get(self.followed) if self.followed is not None else None
        if followed is not None and _playing(followed, event.timestamp):
            return False
        before, self.followed = self.followed, event.device_number
        return before != self.followed

    def any_playing(self, now: float) -> bool:
        return any(_playing(deck, now) for deck in self._decks.values())

    def forget(self, now: float) -> None:
        """Forget the decks quiet for longer than a set's gap: that set is over."""
        for number in [n for n, deck in self._decks.items() if now - deck.heard_at > SET_GAP_S]:
            del self._decks[number]
        if self.followed not in self._decks:
            self.followed = None

    def views(self, now: float, *, master: int | None) -> tuple[DeckView, ...]:
        return tuple(
            DeckView(
                number=deck.number,
                player=deck.player,
                state="playing" if _playing(deck, now) else "cued",
                bpm=deck.track_bpm,
                pitch_percent=deck.pitch_percent,
                master=deck.number == master,
            )
            for deck in sorted(self._decks.values(), key=lambda deck: deck.number)
        )


def _playing(deck: _Deck, now: float) -> bool:
    return now - deck.heard_at <= QUIET_S
