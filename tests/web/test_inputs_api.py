"""The tempo clock's controls and GET /inputs (web spec §12.3; engine spec §7.2)."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from datetime import timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from api_home import Api, api_home
from tempo_fakes import PLAYER, START_WALL, beat_event

from dj_ledfx.tempo.model import DjSet, TempoSettings
from dj_ledfx.tempo.store import TempoStore


@pytest_asyncio.fixture
async def api(tmp_path: Path) -> AsyncIterator[Api]:
    async with api_home(tmp_path, [], []) as api:
        yield api


async def test_with_no_dj_the_inputs_show_the_internal_clock(api: Api) -> None:
    inputs = (await api.client.get("/api/inputs")).json()

    assert inputs["tempo"] == {
        "source": "internal",
        "lock": "auto",
        "bpm": 120.0,
        "stale": False,
        "held": False,
        "internal": {"bpm": 120.0, "how": "default", "at": None},
    }
    assert inputs["prodjlink"] == {
        "state": "idle",
        "interface": None,
        "lastSet": None,
        "decks": [],
    }


async def test_a_bpm_sets_the_internal_clock_and_is_saved(api: Api) -> None:
    answer = await api.client.put("/api/inputs/tempo", json={"lock": "internal", "bpm": 124.5})

    assert answer.status_code == 200
    tempo = answer.json()
    assert (tempo["lock"], tempo["source"], tempo["bpm"]) == ("internal", "internal", 124.5)
    assert tempo["internal"]["how"] == "set"
    saved = await TempoStore(api.home.db).load()
    assert (saved.lock, saved.internal.bpm) == ("internal", 124.5)


@pytest.mark.parametrize(
    "body",
    [
        b'{"lock": "auto", "bpm": NaN}',
        b'{"lock": "auto", "bpm": 1e400}',
        b'{"lock": "auto", "bpm": 29.9}',
        b'{"lock": "auto", "bpm": 300.1}',
        b'{"lock": "auto", "bpm": "fast"}',
        b'{"lock": "sometimes"}',
        b'{"bpm": 120}',
    ],
)
async def test_a_bad_tempo_is_refused_and_changes_nothing(api: Api, body: bytes) -> None:
    answer = await api.client.put(
        "/api/inputs/tempo", content=body, headers={"content-type": "application/json"}
    )

    assert answer.status_code == 422
    assert api.home.tempo.settings() == TempoSettings()


async def test_taps_set_the_tempo_from_the_client_s_times(api: Api) -> None:
    for k in range(4):
        answer = await api.client.post(
            "/api/inputs/tempo/tap", json={"clientTime": 1_790_000_000.0 + 0.4 * k}
        )

    tempo = answer.json()
    assert tempo["bpm"] == pytest.approx(150.0)
    assert (tempo["source"], tempo["held"], tempo["internal"]["how"]) == (
        "internal",
        True,
        "tapped",
    )


async def test_auto_without_a_bpm_releases_a_tap_s_hold(api: Api) -> None:
    tapped = await api.client.post("/api/inputs/tempo/tap")  # no body: the server's time
    assert tapped.json()["held"] is True

    released = await api.client.put("/api/inputs/tempo", json={"lock": "auto"})

    assert released.json()["held"] is False


async def test_a_nudge_holds_the_internal_clock_and_a_wild_one_is_refused(api: Api) -> None:
    nudged = await api.client.post("/api/inputs/tempo/nudge", json={"delta": 0.25})
    wild = [
        await api.client.post("/api/inputs/tempo/nudge", json={"delta": 2}),
        await api.client.post(
            "/api/inputs/tempo/nudge",
            content=b'{"delta": NaN}',
            headers={"content-type": "application/json"},
        ),
    ]

    assert nudged.status_code == 200 and nudged.json()["held"] is True
    assert [answer.status_code for answer in wild] == [422, 422]


async def test_a_bpm_with_a_lock_that_isn_t_on_is_a_bad_request(api: Api) -> None:
    answer = await api.client.put("/api/inputs/tempo", json={"lock": "prodjlink", "bpm": 128})

    assert answer.status_code == 400  # not 409: nothing is locked
    assert answer.json()["detail"] == "A BPM can only be set with Auto or Internal"
    assert api.home.tempo.settings() == TempoSettings()


async def test_internal_controls_are_refused_under_a_pro_dj_link_lock(api: Api) -> None:
    await api.client.put("/api/inputs/tempo", json={"lock": "prodjlink"})

    refused = [
        await api.client.put("/api/inputs/tempo", json={"lock": "prodjlink", "bpm": 100}),
        await api.client.post("/api/inputs/tempo/tap", json={"clientTime": 10.0}),
        await api.client.post("/api/inputs/tempo/nudge", json={"delta": 0.25}),
    ]

    assert [answer.status_code for answer in refused] == [409, 409, 409]
    assert "Pro DJ Link" in refused[1].json()["detail"]
    assert api.home.tempo.internal.how == "default"


async def test_a_dj_shows_in_the_inputs(api: Api) -> None:
    api.home.tempo.listening_on = "0.0.0.0:50001"
    api.home.tempo.on_beat(beat_event(time.monotonic(), bpm=124.0, deck=2, pitch_percent=1.2))

    inputs = (await api.client.get("/api/inputs")).json()

    assert (inputs["tempo"]["source"], inputs["prodjlink"]["state"]) == ("prodjlink", "connected")
    assert inputs["tempo"]["bpm"] == pytest.approx(124.0 * 1.012)
    assert inputs["prodjlink"]["interface"] == "0.0.0.0:50001"
    assert inputs["prodjlink"]["decks"] == [
        {
            "number": 2,
            "player": PLAYER,
            "state": "playing",
            "bpm": 124.0,
            "pitch_percent": 1.2,
            "master": True,
        }
    ]


async def test_the_last_dj_set_reads_from_and_to(api: Api) -> None:
    dj_set = DjSet(started=START_WALL, ended=START_WALL + timedelta(hours=2))
    await TempoStore(api.home.db).save(TempoSettings(last_set=dj_set))
    await api.home.tempo.reload()

    inputs = (await api.client.get("/api/inputs")).json()

    assert inputs["prodjlink"]["lastSet"] == {
        "from": "2026-10-01T19:00:00Z",
        "to": "2026-10-01T21:00:00Z",
    }


async def test_a_nan_comes_back_as_text_in_the_422(api: Api) -> None:
    answer = await api.client.put(
        "/api/inputs/tempo",
        content=b'{"lock": "auto", "bpm": NaN}',
        headers={"content-type": "application/json"},
    )

    [error] = answer.json()["detail"]
    assert (error["loc"], error["input"]) == (["body", "bpm"], "nan")
