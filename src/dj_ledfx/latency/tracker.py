from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol

from loguru import logger

from dj_ledfx.latency.doze import DozeCheck
from dj_ledfx.latency.strategies import ProbeStrategy, StaticLatency, make_strategy

# A round trip that arrives within this long of a send was measured while the light streamed.
STREAMING_WINDOW_S = 0.5


class LatencyTracker:
    """A light's latency: one-way network time from its strategy, plus the time the light
    takes to show a frame it has (display_ms), plus the owner's offset. The doze check
    (light-sync spec §5) says how much of a round trip is one way: all of a dozing light's,
    whose frames wait for its wakes while its replies come straight back, and half of an
    awake light's."""

    def __init__(
        self,
        strategy: ProbeStrategy,
        manual_offset_ms: float = 0.0,
        *,
        display_ms: float = 0.0,
        clock: Callable[[], float] = time.monotonic,
        name: str = "A light",
    ) -> None:
        self._strategy = strategy
        self._manual_offset_ms = manual_offset_ms
        self._display_ms = display_ms
        self._clock = clock
        self._name = name
        self._last_send: float | None = None
        self._measured = False
        self._doze = DozeCheck()

    @property
    def name(self) -> str:
        """The light's name, for the log."""
        return self._name

    @property
    def manual_offset_ms(self) -> float:
        return self._manual_offset_ms

    @manual_offset_ms.setter
    def manual_offset_ms(self, value: float) -> None:
        self._manual_offset_ms = value

    @property
    def link_latency_ms(self) -> float:
        """The strategy's latency: the network's part, before the display delay and the
        offset. A light's link memory keeps it (spec §7)."""
        return self._strategy.get_latency()

    @property
    def effective_latency_ms(self) -> float:
        return self.link_latency_ms + self._display_ms + self._manual_offset_ms

    @property
    def effective_latency_s(self) -> float:
        return self.effective_latency_ms / 1000.0

    @property
    def dozing(self) -> bool:
        """Whether the doze check calls the light's Wi-Fi dozing."""
        return self._doze.dozing

    @property
    def measured(self) -> bool:
        """Whether a round trip measured while the light streamed has landed since the last
        reset or recall. Until one has, the latency is the seed (the config's, or the type's
        heuristic) or the one the light had before."""
        return self._measured

    @property
    def streaming(self) -> bool:
        """Whether a frame went out within STREAMING_WINDOW_S: a round trip measured now
        counts, so only then is the light worth a probe."""
        last = self._last_send
        return last is not None and self._clock() - last <= STREAMING_WINDOW_S

    def note_send(self) -> None:
        """A frame went out now, on this tracker's clock."""
        self._last_send = self._clock()

    def update_rtt(self, rtt_ms: float) -> None:
        """A probe's round trip, counted only while the light streams: an idle light's Wi-Fi
        dozes, and its round trips run long. The strategy takes all of a dozing light's round
        trip and half of an awake light's; when the doze check changes the light's mode, the
        strategy starts again from the round trips the check holds, at the new share."""
        if not self.streaming:
            return
        if self._doze.add(self._clock(), rtt_ms):
            self._log_mode()
            self._strategy.reset()
            for held in self._doze.round_trips:
                self._strategy.update(held * self._share)
        else:
            self._strategy.update(rtt_ms * self._share)
        # A static latency ignores the sample: it stays the configured one.
        self._measured = not isinstance(self._strategy, StaticLatency)

    def recall(self, latency_ms: float, dozing: bool) -> None:
        """Start from a latency and mode the light had before (spec §7): the strategy's
        latency_ms (a static strategy keeps its own), and its mode. The round trips held
        go, so the doze check starts again from the next."""
        self._strategy.reset(latency_ms)
        self._doze = DozeCheck(dozing=dozing)
        self._measured = False

    def reset(self) -> None:
        """The light came back: it starts again from the latency and mode it has now."""
        self.recall(self.link_latency_ms, self.dozing)
        self._last_send = None

    @property
    def _share(self) -> float:
        """How much of a round trip is one way."""
        return 1.0 if self._doze.dozing else 0.5

    def _log_mode(self) -> None:
        reading = self._doze.reading()
        assert reading is not None  # the mode changes only over enough round trips
        if self._doze.dozing:
            message = "{} dozes (z {:.1f}, median round trip {:.0f} ms over {}): its latency is"
            message += " its whole round trip"
        else:
            message = "{} is awake (z {:.1f}, median round trip {:.0f} ms over {}): its latency"
            message += " is half its round trip"
        logger.info(message, self._name, reading.z, reading.median_ms, reading.replies)


class LatencyConfig(Protocol):
    """A kind of device's latency settings: OpenRGB's, LIFX's and Govee's configs all have them."""

    @property
    def latency_strategy(self) -> str: ...
    @property
    def latency_ms(self) -> float: ...
    @property
    def latency_window_size(self) -> int: ...
    @property
    def manual_offset_ms(self) -> float: ...


def tracker_for(
    cfg: LatencyConfig,
    *,
    seed_ms: float | None = None,
    display_ms: float = 0.0,
    name: str = "A light",
) -> LatencyTracker:
    """A device's tracker, as its kind's config says: the strategy it names, seeded at
    seed_ms (else the config's latency_ms), its window and offset, plus how long the light
    takes to show a frame (display_ms). name is the light's, for the log."""
    seed = cfg.latency_ms if seed_ms is None else seed_ms
    strategy = make_strategy(cfg.latency_strategy, seed, cfg.latency_window_size)
    return LatencyTracker(strategy, cfg.manual_offset_ms, display_ms=display_ms, name=name)
