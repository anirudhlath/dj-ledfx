from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from api_home import Api, api_home
from conftest import FakeLight

from dj_ledfx.looks.model import Look
from dj_ledfx.zones.model import ZoneRecord

DESK = ZoneRecord(id="desk", name="Desk", lights=("a",))


def _mine(api: Api) -> Look:
    breathe = api.home.look("classic-breathe")
    return replace(breathe, name="My breathe", built_in=False, derived_from=breathe.id)


async def test_restore_brings_back_zones_looks_stars_and_what_ran(tmp_path: Path) -> None:
    (tmp_path / "old").mkdir()
    (tmp_path / "new").mkdir()
    async with api_home(tmp_path / "old", [FakeLight("a")], [DESK]) as old:
        mine = await old.home.looks.create(_mine(old))
        await old.home.looks.set_starred(mine.id, True)
        await old.home.manager.start("desk", mine)
        await old.home.manager.set_brightness("desk", 0.5)
        await old.home.db.save_preset("Slow", "breathe", json.dumps({"beats_per_cycle": 8}))
        backup = (await old.client.get("/api/state/export")).text

    async with api_home(tmp_path / "new", [FakeLight("a")], []) as new:
        resp = await new.client.post("/api/state/import", content=backup)

        assert resp.status_code == 200
        assert [zone.id for zone in new.home.manager.zones()] == ["desk"]
        assert new.home.looks.get(mine.id).name == "My breathe"
        assert new.home.looks.is_starred(mine.id)
        running = [(r.zone_id, r.look_id, r.brightness) for r in new.home.manager.running()]
        assert running == [("desk", mine.id, 0.5)]
        assert "desk" in new.home.host.runtimes
        assert [p["name"] for p in await new.home.db.load_presets()] == ["Slow"]


# B6: a restored look is applied as a start is: its lights end up on and running.
async def test_restored_looks_switch_their_lights_on_and_run(tmp_path: Path) -> None:
    lamp = FakeLight("a", power=False)
    async with api_home(tmp_path, [lamp], [DESK]) as api:
        await api.home.manager.start("desk", api.home.look("classic-breathe"))
        backup = (await api.client.get("/api/state/export")).text

        resp = await api.client.post("/api/state/import", content=backup)

        assert resp.status_code == 200
        assert [r.zone_id for r in api.home.manager.running()] == ["desk"]
        assert lamp.power is True
        assert api.home.routes.routes["a"].streaming


async def test_restoring_stops_what_runs_here_first(tmp_path: Path) -> None:
    kitchen = ZoneRecord(id="kitchen", name="Kitchen", lights=("b",))
    lights = [FakeLight("a"), FakeLight("b")]
    async with api_home(tmp_path, lights, [DESK, kitchen]) as api:
        await api.home.manager.start("kitchen", api.home.look("classic-breathe"))

        resp = await api.client.post("/api/state/import", content="")

        assert resp.status_code == 200
        assert api.home.manager.running() == []
        assert ("restore", b"before") in api.home.lights["b"].calls
        assert [zone.id for zone in api.home.manager.zones()] == ["desk", "kitchen"]


async def test_a_file_that_is_not_toml_changes_nothing(tmp_path: Path) -> None:
    async with api_home(tmp_path, [FakeLight("a")], [DESK]) as api:
        await api.home.manager.start("desk", api.home.look("classic-breathe"))

        resp = await api.client.post("/api/state/import", content="this is = = not toml")

        assert resp.status_code == 400
        assert resp.json()["detail"].startswith("Invalid TOML: ")
        assert [r.zone_id for r in api.home.manager.running()] == ["desk"]
