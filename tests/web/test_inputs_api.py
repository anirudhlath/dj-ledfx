"""The tempo clock's controls and GET /inputs (web spec §12.3; engine spec §7.2)."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from api_home import Api, api_home
from fastapi.testclient import TestClient
from sun_fakes import AT_DUSK, FixedSun
from tempo_fakes import PLAYER, START_WALL, FakeTime, beat_event, tempo_clock

from dj_ledfx.home.sun import SunPoint, SunReading
from dj_ledfx.prodjlink.listener import Listening
from dj_ledfx.tempo.model import DjSet, TempoSettings
from dj_ledfx.tempo.store import TempoStore
from dj_ledfx.web.app import create_app
from tests.web.conftest import mock_deps, raw_json, until


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
    answer = await api.client.put("/api/inputs/tempo", **raw_json(body))

    assert answer.status_code == 422
    assert api.home.tempo.settings() == TempoSettings()


async def test_taps_set_the_tempo_from_the_client_s_times(api: Api) -> None:
    sent = time.time()  # the client's clock: within a day of the server's
    for k in range(4):
        tap = {"clientTime": sent + 0.4 * k}
        answer = await api.client.post("/api/inputs/tempo/tap", json=tap)

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
        await api.client.post("/api/inputs/tempo/nudge", **raw_json(b'{"delta": NaN}')),
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


async def test_a_dj_shows_in_the_inputs(tmp_path: Path) -> None:
    async with api_home(tmp_path, [], [], listening=Listening("0.0.0.0:50001")) as api:
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


async def test_a_port_that_can_t_be_bound_shows_pro_dj_link_disconnected(tmp_path: Path) -> None:
    async with api_home(tmp_path, [], [], listening=Listening(failed=True)) as api:
        inputs = (await api.client.get("/api/inputs")).json()

    assert (inputs["prodjlink"]["state"], inputs["prodjlink"]["interface"]) == (
        "disconnected",
        None,
    )
    assert inputs["tempo"]["source"] == "internal"  # the internal clock keeps the tempo


async def test_the_last_dj_set_reads_from_and_to(api: Api) -> None:
    dj_set = DjSet(started=START_WALL, ended=START_WALL + timedelta(hours=2))
    await TempoStore(api.home.db).save(TempoSettings(last_set=dj_set))
    await api.home.tempo.reload()

    inputs = (await api.client.get("/api/inputs")).json()

    assert inputs["prodjlink"]["lastSet"] == {
        "from": "2026-10-01T19:00:00Z",
        "to": "2026-10-01T21:00:00Z",
    }


def _a_day_in_march(sunrise: datetime | None, sunset: datetime | None) -> SunReading:
    """A reading at made-up numbers (no place's): the sun low in the west, two path points."""
    at = datetime(2026, 3, 20, 18, 0, tzinfo=UTC)
    return SunReading(
        now=SunPoint(at, 2.14, 268.06),
        sunrise=sunrise,
        sunset=sunset,
        path=(
            SunPoint(at - timedelta(minutes=20), 6.04, 262.52),
            SunPoint(at - timedelta(minutes=10), 4.06, 265.34),
        ),
    )


async def test_inputs_carry_the_sun_with_its_day_and_path(tmp_path: Path) -> None:
    sunrise = datetime(2026, 3, 20, 6, 2, 30, tzinfo=UTC)
    sunset = datetime(2026, 3, 20, 18, 10, tzinfo=UTC)
    sun = FixedSun(AT_DUSK, _a_day_in_march(sunrise, sunset))
    async with api_home(tmp_path, [], [], sun=sun) as api:
        inputs = (await api.client.get("/api/inputs")).json()

    assert inputs["sun"] == {
        "elevation": 2.1,
        "azimuth": 268.1,
        "sunrise": "2026-03-20T06:02:30Z",
        "sunset": "2026-03-20T18:10:00Z",
        "path": [
            {"at": "2026-03-20T17:40:00Z", "elevation": 6.0, "azimuth": 262.5},
            {"at": "2026-03-20T17:50:00Z", "elevation": 4.1, "azimuth": 265.3},
        ],
    }


@pytest.mark.parametrize("sun", [None, FixedSun(None)], ids=["no-sun", "no-location"])
async def test_inputs_say_no_sun_as_null(tmp_path: Path, sun: FixedSun | None) -> None:
    async with api_home(tmp_path, [], [], sun=sun) as api:
        inputs = (await api.client.get("/api/inputs")).json()

    assert "sun" in inputs
    assert inputs["sun"] is None


async def test_a_polar_sun_has_null_sunrise_and_sunset(tmp_path: Path) -> None:
    sun = FixedSun(AT_DUSK, _a_day_in_march(None, None))
    async with api_home(tmp_path, [], [], sun=sun) as api:
        inputs = (await api.client.get("/api/inputs")).json()

    assert (inputs["sun"]["sunrise"], inputs["sun"]["sunset"]) == (None, None)
    assert inputs["sun"]["elevation"] == 2.1  # the sun itself is still sent


def test_the_inputs_channel_carries_the_sun() -> None:
    sunset = datetime(2026, 3, 20, 18, 10, tzinfo=UTC)
    sun = FixedSun(AT_DUSK, _a_day_in_march(None, sunset))
    app = create_app(**mock_deps(sun=sun))
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        pushed = until(ws, "inputs")["inputs"]["sun"]
        asked = client.get("/api/inputs").json()["sun"]

    assert pushed == asked
    assert pushed["elevation"] == 2.1
    assert (pushed["sunrise"], pushed["sunset"]) == (None, "2026-03-20T18:10:00Z")


async def test_a_nan_comes_back_as_text_in_the_422(api: Api) -> None:
    answer = await api.client.put("/api/inputs/tempo", **raw_json(b'{"lock": "auto", "bpm": NaN}'))

    [error] = answer.json()["detail"]
    assert (error["loc"], error["input"]) == (["body", "bpm"], "nan")


# M3 review ruling: a tap's time is a hint. Taps arrive 0.4 s apart (150 BPM), and a
# client time the clock can use says 0.5 s (120 BPM).
WALL = START_WALL.timestamp()  # the server's clock at the first tap
DAY = 86_400.0
CLIENT_TIMES = [
    pytest.param(lambda k: "NaN", 150.0, id="nan"),
    pytest.param(None, 150.0, id="missing"),
    pytest.param(lambda k: "1e20", 150.0, id="1e20"),
    pytest.param(lambda k: f"{WALL - 1.5 * DAY + 0.5 * k}", 150.0, id="a-day-and-a-half-off"),
    pytest.param(lambda k: f"{WALL + 3600.0 + 0.5 * k}", 120.0, id="an-hour-off"),
]


@pytest.mark.parametrize(("client_time", "bpm"), CLIENT_TIMES)
def test_a_tap_s_time_counts_only_when_the_clock_can_use_it(
    client_time: Callable[[int], str] | None, bpm: float
) -> None:
    fake = FakeTime()
    app = create_app(**mock_deps(tempo=tempo_clock(fake)))
    with TestClient(app) as client:
        for k in range(4):
            body = "{}" if client_time is None else f'{{"clientTime": {client_time(k)}}}'
            answer = client.post("/api/inputs/tempo/tap", **raw_json(body))
            fake.now += 0.4

    assert answer.status_code == 200
    assert answer.json()["bpm"] == pytest.approx(bpm)


@pytest.mark.parametrize(("client_time", "bpm"), CLIENT_TIMES)
def test_a_socket_tap_s_time_counts_only_when_the_clock_can_use_it(
    client_time: Callable[[int], str] | None, bpm: float
) -> None:
    fake = FakeTime()
    app = create_app(**mock_deps(tempo=tempo_clock(fake)))
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        for k in range(4):
            sent = "" if client_time is None else f', "client_time": {client_time(k)}'
            ws.send_text(f'{{"action": "tap", "id": {k}{sent}}}')
            assert until(ws, "ack")["id"] == k
            fake.now += 0.4

    assert app.state.tempo.bpm == pytest.approx(bpm)
