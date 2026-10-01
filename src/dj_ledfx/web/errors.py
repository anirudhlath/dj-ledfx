"""Zone, look, home and tempo errors as HTTP answers, with the reason for the web app to show."""

from __future__ import annotations

import math
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from dj_ledfx.home.model import HomeError, HomeNotFoundError
from dj_ledfx.looks.model import BuiltInLookError, LookError, LookNotFoundError
from dj_ledfx.tempo.model import TempoError, TempoLockedError
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
    except (ZoneNotRunningError, BuiltInLookError, TempoLockedError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except HomeError as exc:  # ShapeError too
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (ZoneError, LookError, TempoError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def unprocessable(request: Request, exc: RequestValidationError) -> JSONResponse:
    """FastAPI's 422, but a NaN or an infinity the request sent comes back as text. JSON
    can't carry them, so FastAPI's own answer fails and the client gets a 500."""
    detail = jsonable_encoder(exc.errors(), custom_encoder={float: _finite_or_text})
    return JSONResponse(status_code=422, content={"detail": detail})


def _finite_or_text(value: float) -> float | str:
    return value if math.isfinite(value) else str(value)
