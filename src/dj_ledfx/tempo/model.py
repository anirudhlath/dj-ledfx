"""The tempo clock's vocabulary (spec §7.2; web spec §11.5 and §12.3–12.4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, get_args

from dj_ledfx.types import is_finite_number

TempoSource = Literal["prodjlink", "music", "internal"]
TempoLock = Literal["auto", "prodjlink", "music", "internal"]
InternalHow = Literal["default", "set", "tapped", "kept"]
DeckState = Literal["empty", "cued", "playing"]

LOCKS: tuple[TempoLock, ...] = get_args(TempoLock)
UNLOCKED: frozenset[TempoLock] = frozenset({"auto", "internal"})  # the internal controls work
HOWS: tuple[InternalHow, ...] = get_args(InternalHow)
SOURCE_NAMES: dict[str, str] = {
    "prodjlink": "Pro DJ Link",
    "music": "Music",
    "internal": "Internal",
}

MIN_BPM = 30.0
MAX_BPM = 300.0
DEFAULT_BPM = 120.0
BEATS_PER_BAR = 4
QUIET_S = 2.0  # a deck heard this recently is playing; a source quiet this long hands back
SET_GAP_S = 1800.0  # 30 min of silence ends a DJ set, and its decks are forgotten
MAX_NUDGE_BEATS = 1.0


class TempoError(ValueError):
    """A tempo control the clock can't take."""


class TempoLockedError(TempoError):
    """An internal control (a BPM, a tap, a nudge) while a lock keeps the internal clock out."""

    def __init__(self, lock: TempoLock) -> None:
        name = SOURCE_NAMES.get(lock, lock)
        super().__init__(f"The tempo is locked to {name}: choose Auto or Internal to set it here")
        self.lock = lock


def check_bpm(bpm: object) -> float:
    """The BPM as a float, or TempoError when it isn't a finite number from 30 to 300."""
    if not is_finite_number(bpm):
        raise TempoError("A tempo must be a finite number")
    if not MIN_BPM <= bpm <= MAX_BPM:
        raise TempoError(f"A tempo is {MIN_BPM:g} to {MAX_BPM:g} BPM, not {bpm:g}")
    return float(bpm)


@dataclass(frozen=True, slots=True)
class InternalTempo:
    """The internal clock's BPM, how it got it and when: the Inputs page's
    "118.0 · tapped 19:10" (web spec §8.8). "default" has no time."""

    bpm: float = DEFAULT_BPM
    how: InternalHow = "default"
    at: datetime | None = None


@dataclass(frozen=True, slots=True)
class DjSet:
    """From the first beat a DJ played to the last, gaps under SET_GAP_S included."""

    started: datetime
    ended: datetime


@dataclass(frozen=True, slots=True)
class TempoSettings:
    """What the clock keeps in state.db and backups (M3 ruling 9)."""

    lock: TempoLock = "auto"
    internal: InternalTempo = field(default_factory=InternalTempo)
    last_set: DjSet | None = None


@dataclass(frozen=True, slots=True)
class TempoSample:
    """The clock at one moment: spec §4.2's beat fields and web spec §12.4's beat."""

    bpm: float
    beat_phase: float  # 0..1 within the beat
    bar_phase: float  # 0..1 within the bar
    beat_index: int  # beats since the clock started counting
    bar_index: int
    beat_in_bar: int  # 1–4, like v1's beat_pos
    pitch_percent: float
    source: TempoSource
    stale: bool


@dataclass(frozen=True, slots=True)
class DeckView:
    """A player as the decks channel shows it (web spec §12.4)."""

    number: int
    player: str
    state: DeckState
    bpm: float | None  # the track's; its pitch is apart (M3 ruling 5)
    pitch_percent: float
    master: bool  # the deck the clock follows (M3 ruling 4)


@dataclass(frozen=True, slots=True)
class TempoChanged:
    """The tempo's source, lock, BPM, hold or settings changed: the inputs channel."""


@dataclass(frozen=True, slots=True)
class DecksChanged:
    """A deck appeared, changed, went quiet or was forgotten: the decks channel."""
