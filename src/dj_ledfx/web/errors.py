"""Zone and look errors as HTTP answers, with the reason for the web app to show."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import HTTPException

from dj_ledfx.home.model import HomeError, HomeNotFoundError
from dj_ledfx.looks.model import BuiltInLookError, LookError, LookNotFoundError
from dj_ledfx.zones.model import ZoneError, ZoneNotFoundError, ZoneNotRunningError
from dj_ledfx.zones.preview import PreviewNotFoundError


@contextmanager
def answers() -> Iterator[None]:
    try:
        yield
    except HomeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc
    except ZoneNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"No zone '{exc.args[0]}'") from exc
    except LookNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"No look '{exc.args[0]}'") from exc
    except PreviewNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"No preview '{exc.args[0]}'") from exc
    except (ZoneNotRunningError, BuiltInLookError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except HomeError as exc:  # ShapeError too
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (ZoneError, LookError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
