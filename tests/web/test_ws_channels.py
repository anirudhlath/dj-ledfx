"""Pushed WebSocket channels (web spec §12.4): the current state on connect, then changes."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from api_home import Api, api_home
from conftest import FakeLight
from tempo_fakes import PLAYER, beat_event

from dj_ledfx.tempo.model import TempoChanged
from dj_ledfx.web import ws as hub
from dj_ledfx.web.ws import Session, event_broadcast, initial_messages
from dj_ledfx.zones.model import ZoneRecord, ZonesChanged


class FakeSocket:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []
        self.sent_at: list[float] = []  # each message's loop time

    async def send_text(self, text: str) -> None:
        self.messages.append(json.loads(text))
        self.sent_at.append(asyncio.get_running_loop().time())

    def on(self, channel: str) -> list[dict[str, Any]]:
        return [message for message in self.messages if message["channel"] == channel]

    def times_on(self, channel: str) -> list[float]:
        sent = zip(self.sent_at, self.messages, strict=True)
        return [at for at, message in sent if message["channel"] == channel]


async def until(condition: Callable[[], bool]) -> None:
    async with asyncio.timeout(1.0):
        while not condition():
            await asyncio.sleep(0.01)


@pytest_asyncio.fixture
async def api(tmp_path: Path) -> AsyncIterator[Api]:
    zones = [ZoneRecord(id="desk", name="Desk", lights=("a",))]
    async with api_home(tmp_path, [FakeLight("a")], zones) as api:
        yield api


@asynccontextmanager
async def broadcasting(app: Any, *clients: FakeSocket) -> AsyncIterator[None]:
    """The app's event broadcaster running, with these clients connected."""
    for client in clients:
        app.state.ws_sessions.add(Session(client))  # type: ignore[arg-type]
    task = asyncio.create_task(event_broadcast(app))
    await asyncio.sleep(0)  # let it subscribe
    try:
        yield
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest_asyncio.fixture
async def socket(api: Api) -> AsyncIterator[FakeSocket]:
    """A connected client, with the app's event broadcaster running."""
    fake = FakeSocket()
    async with broadcasting(api.app, fake):
        yield fake


async def test_running_zones_are_pushed_when_they_change(api: Api, socket: FakeSocket) -> None:
    await api.client.post("/api/zones/desk/start", json={"lookId": "classic-breathe"})
    await until(lambda: bool(socket.on("running")))

    [message] = socket.on("running")
    assert [zone["zoneId"] for zone in message["zones"]] == ["desk"]
    assert message["zones"][0]["lookName"] == "Breathe"
    assert message["overlays"] == []


async def test_a_transition_is_pushed_as_it_starts(api: Api, socket: FakeSocket) -> None:
    body = {"lookId": "classic-breathe", "transition": {"kind": "fade", "durationS": 2.0}}
    await api.client.post("/api/zones/desk/start", json=body)
    await until(lambda: bool(socket.on("running")))

    [message] = socket.on("running")
    [zone] = message["zones"]
    assert zone["state"] == "transition"
    assert zone["transition"] == {"from": "", "kind": "fade", "progress": 0.0, "durationS": 2.0}


async def test_changes_that_arrive_together_are_pushed_once(api: Api, socket: FakeSocket) -> None:
    api.home.bus.emit(ZonesChanged())
    api.home.bus.emit(ZonesChanged())
    await until(lambda: bool(socket.on("running")))
    await asyncio.sleep(0.05)

    assert len(socket.on("running")) == 1


async def test_a_client_that_connects_gets_the_current_state(api: Api) -> None:
    await api.client.post("/api/zones/desk/start", json={"lookId": "classic-breathe"})

    messages = {message["channel"]: message for message in initial_messages(api.app)}

    assert [zone["zoneId"] for zone in messages["running"]["zones"]] == ["desk"]


async def test_light_statuses_are_pushed_when_they_change(api: Api, socket: FakeSocket) -> None:
    await api.client.post("/api/zones/desk/start", json={"lookId": "classic-breathe"})
    await until(lambda: bool(socket.on("lights")))

    assert socket.on("lights")[-1]["lights"] == [
        {
            "id": "a",
            "status": "streaming",
            "statusSince": "2026-09-24T19:00:00Z",
            "ownEffect": None,
            "power": None,
            "colour": None,
        }
    ]


async def test_attention_is_pushed_when_the_list_changes(api: Api, socket: FakeSocket) -> None:
    await api.client.post("/api/zones/desk/start", json={"lookId": "classic-breathe"})
    api.home.devices.demote_device("a")
    api.monitor.refresh()
    api.home.clock[0] += timedelta(minutes=2)
    api.feed.update()
    await until(lambda: bool(socket.on("attention")))

    [message] = socket.on("attention")
    assert [item["kind"] for item in message["items"]] == ["light-offline"]


async def test_a_client_that_connects_gets_every_pushed_channel(api: Api) -> None:
    api.monitor.refresh()

    channels = [message["channel"] for message in initial_messages(api.app)]

    assert channels == ["running", "lights", "attention", "transport", "decks", "inputs"]


async def test_preview_only_is_pushed_as_the_transport_state(api: Api, socket: FakeSocket) -> None:
    await api.home.manager.set_preview_only(True)
    await until(lambda: bool(socket.on("transport")))

    assert socket.on("transport") == [{"channel": "transport", "state": "simulating"}]


async def test_decks_and_inputs_are_pushed_when_a_dj_starts(api: Api, socket: FakeSocket) -> None:
    api.home.tempo.on_beat(beat_event(time.monotonic(), deck=2))
    await until(lambda: bool(socket.on("decks")) and bool(socket.on("inputs")))

    assert socket.on("decks")[-1]["decks"] == [
        {
            "number": 2,
            "player": PLAYER,
            "state": "playing",
            "bpm": 128.0,
            "pitch_percent": 0.0,
            "master": True,
        }
    ]
    assert socket.on("inputs")[-1]["inputs"]["prodjlink"]["state"] == "connected"


async def test_the_inputs_are_pushed_when_the_tempo_is_set(api: Api, socket: FakeSocket) -> None:
    await api.client.put("/api/inputs/tempo", json={"lock": "auto", "bpm": 98.0})
    await until(lambda: bool(socket.on("inputs")))

    [message] = socket.on("inputs")
    assert message["inputs"]["tempo"]["bpm"] == 98.0
    assert message["inputs"]["tempo"]["internal"]["how"] == "set"


async def test_one_inputs_heartbeat_serves_every_client(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hub, "INPUTS_HEARTBEAT_S", 0.05)
    built: list[dict[str, Any]] = []
    snapshot = hub._SNAPSHOTS["inputs"]

    def counted(app: Any) -> dict[str, Any] | None:
        message = snapshot(app)
        built.append(message)
        return message

    monkeypatch.setitem(hub._SNAPSHOTS, "inputs", counted)
    tabs = [FakeSocket(), FakeSocket(), FakeSocket()]
    async with broadcasting(api.app, *tabs):
        await until(lambda: len(tabs[0].on("inputs")) >= 3)

    heard = tabs[0].on("inputs")
    assert all(tab.on("inputs")[:3] == heard[:3] for tab in tabs)
    assert heard[0]["inputs"]["tempo"]["source"] == "internal"
    # one snapshot a beat for all three tabs (the last may still have been on its way)
    assert len(heard) <= len(built) <= len(heard) + 1


async def test_no_inputs_heartbeat_right_after_a_push(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hub, "INPUTS_HEARTBEAT_S", 0.2)
    fake = FakeSocket()
    async with broadcasting(api.app, fake):
        await asyncio.sleep(0.1)
        before = len(fake.on("inputs"))
        api.home.bus.emit(TempoChanged())
        await until(lambda: len(fake.on("inputs")) >= before + 2)

    pushed, following = fake.times_on("inputs")[before : before + 2]
    assert following - pushed >= 0.2
