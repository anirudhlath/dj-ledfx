"""Zone and look errors as HTTP answers, with the reason for the web app to show."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import HTTPException

from dj_ledfx.looks.model import LookError, LookNotFoundError
from dj_ledfx.zones.model import ZoneError, ZoneNotFoundError, ZoneNotRunningError


@contextmanager
def answers() -> Iterator[None]:
    try:
        yield
    except ZoneNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"No zone '{exc.args[0]}'") from exc
    except LookNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"No look '{exc.args[0]}'") from exc
    except ZoneNotRunningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ZoneError, LookError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
