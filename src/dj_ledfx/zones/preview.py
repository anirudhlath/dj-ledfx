"""The web app's preview (spec §4.1; web spec §12.3 /preview).

One preview at a time: a new one replaces the last (ruling 9). The zone manager makes and
hosts the preview's runtime (ZoneManager.start_preview): it renders for the web app's
preview stream only, has no route, so it never sends to a light, and is never synced, so
it never captures one. It follows its zone's lights as the map changes and ends with its
zone. A browser tab that closes mid-preview sends no DELETE, so a preview nobody has
watched for PREVIEW_IDLE_S ends by itself (Review Focus 1).
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING

from loguru import logger

from dj_ledfx.looks.model import validate_look
from dj_ledfx.timing import paced

if TYPE_CHECKING:
    from dj_ledfx.looks.model import Look
    from dj_ledfx.zones.manager import ZoneManager
    from dj_ledfx.zones.runtime import ZoneRuntime

PREVIEW_IDLE_S = 10.0


class PreviewNotFoundError(KeyError):
    """No preview has that id: it ended, or a newer one replaced it."""


@dataclass
class _Preview:
    id: str
    runtime: ZoneRuntime
    watched_at: float  # the preview manager's clock


class PreviewManager:
    def __init__(
        self,
        zones: ZoneManager,
        watching: Callable[[], bool],
        *,
        idle_s: float = PREVIEW_IDLE_S,
        check_s: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._zones = zones
        self._watching = watching  # does any client watch the preview stream?
        self._idle_s = idle_s
        self._check_s = check_s
        self._clock = clock
        self._preview: _Preview | None = None

    def runtimes(self) -> list[ZoneRuntime]:
        return [] if self._preview is None else [self._preview.runtime]

    def start(self, zone_id: str, look: Look) -> str:
        """Show a look on a zone in the web app, replacing any preview. A request that
        fails leaves the current preview as it is."""
        preview_id = f"preview-{uuid.uuid4().hex[:8]}"
        runtime = self._zones.start_preview(zone_id, look, partial(self._ended, preview_id))
        self._end()
        self._preview = _Preview(preview_id, runtime, self._clock())
        return preview_id

    def update(self, preview_id: str, look: Look) -> None:
        """The editor changed the look: take it in place where the layers allow."""
        preview = self._require(preview_id)
        validate_look(look)
        preview.runtime.update_look(look)

    def stop(self, preview_id: str) -> None:
        self._require(preview_id)
        self._end()

    def check(self) -> None:
        """End the preview once nobody has watched it for idle_s."""
        preview = self._preview
        if preview is None:
            return
        now = self._clock()
        if self._watching():
            preview.watched_at = now
        elif now - preview.watched_at >= self._idle_s:
            logger.info(
                "Preview {} ended: nobody watched it for {:.0f} s", preview.id, self._idle_s
            )
            self._end()

    async def run(self) -> None:
        await paced(self._check_s, lambda _now: self.check(), lambda: True)

    def close(self) -> None:
        self._end()

    def _ended(self, preview_id: str) -> None:
        """The zone manager ended the preview: its zone is gone or has no lights."""
        if self._preview is not None and self._preview.id == preview_id:
            logger.info("Preview {} ended: its zone is gone or has no lights", preview_id)
            self._preview = None

    def _require(self, preview_id: str) -> _Preview:
        preview = self._preview
        if preview is None or preview.id != preview_id:
            raise PreviewNotFoundError(preview_id)
        return preview

    def _end(self) -> None:
        if self._preview is not None:
            self._zones.end_preview(self._preview.runtime)
            self._preview = None
