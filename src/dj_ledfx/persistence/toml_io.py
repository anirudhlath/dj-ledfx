"""TOML import/export marshaling for StateDB.

Export format:
  [config.<section>]          — config key-value pairs
  [devices."<name>"]          — device records keyed by display name
  [scenes."<id>"]             — scene records
  [scenes."<id>".effect]      — scene effect state
  [scenes."<id>".placements."<device_name>"]  — device placements
  [groups."<name>"]           — group metadata + members
  [presets."<name>"]          — preset records
  [zones."<id>"]              — zones: name, kind, all_lights, lights (stable ids, LED order)
  [looks."<id>"]              — saved looks: body (contract JSON), created_at, updated_at
  [stars]                     — looks = ids of starred looks, built in or saved
  [running."<zone id>"]       — what a zone runs: look_id, look (JSON), brightness,
                                lights, started_at

Import merges into what is there. Zones and looks in the file replace those with the
same id, and each running entry becomes that zone's assignment.
"""

from __future__ import annotations

import dataclasses
import json
import tomllib
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast, get_args

import tomli_w
from loguru import logger

from dj_ledfx.looks.builtin import builtin_looks
from dj_ledfx.looks.store import STAR_LOOK, UPSERT_LOOK
from dj_ledfx.persistence.state_db import StateDB
from dj_ledfx.timing import as_utc, utcnow
from dj_ledfx.types import clamp01
from dj_ledfx.zones.model import Assignment, ZoneKind, ZoneRecord
from dj_ledfx.zones.store import ZoneStore

if TYPE_CHECKING:
    from dj_ledfx.config import AppConfig

# Config sections that belong at the top level (not per-device, not internal)
_EXPORTABLE_CONFIG_SECTIONS = {
    "engine",
    "network",
    "web",
    "devices",
    "discovery",
}


async def export_toml(db: StateDB) -> str:
    """Export entire DB state as structured TOML string."""
    doc: dict[str, Any] = {}

    # --- Config ---
    all_config = await db.load_all_config()
    config_by_section: dict[str, dict[str, Any]] = {}
    for (section, key), value in all_config.items():
        config_by_section.setdefault(section, {})[key] = value

    if config_by_section:
        doc["config"] = config_by_section

    # --- Devices ---
    # Load once and reuse for both the devices section and scene placement name resolution
    devices = await db.load_devices()
    if devices:
        devices_doc: dict[str, Any] = {}
        for device in devices:
            name = device["name"]
            entry: dict[str, Any] = {"backend": device["backend"]}
            if device.get("led_count") is not None:
                entry["led_count"] = device["led_count"]
            if device.get("ip"):
                entry["ip"] = device["ip"]
            if device.get("mac"):
                entry["mac"] = device["mac"]
            if device.get("device_id"):
                entry["device_id"] = device["device_id"]
            if device.get("sku"):
                entry["sku"] = device["sku"]
            if device.get("last_latency_ms") is not None:
                entry["last_latency_ms"] = device["last_latency_ms"]
            devices_doc[name] = entry
        doc["devices"] = devices_doc

    # --- Scenes ---
    scenes = await db.load_scenes()
    if scenes:
        # Build device_id -> name map once for all scene placements
        id_to_name = {d["id"]: d["name"] for d in devices}

        scenes_doc: dict[str, Any] = {}
        for scene in scenes:
            scene_id = scene["id"]
            scene_entry: dict[str, Any] = {"name": scene["name"]}
            if scene.get("mapping_type"):
                scene_entry["mapping_type"] = scene["mapping_type"]
            if scene.get("effect_mode"):
                scene_entry["effect_mode"] = scene["effect_mode"]
            if scene.get("is_active"):
                scene_entry["is_active"] = bool(scene["is_active"])
            if scene.get("mapping_params"):
                scene_entry["mapping_params"] = json.loads(scene["mapping_params"])
            if scene.get("effect_source"):
                scene_entry["effect_source"] = scene["effect_source"]

            # Effect state
            effect_state = await db.load_scene_effect_state(scene_id)
            if effect_state:
                raw = effect_state["params"]
                params = json.loads(raw) if isinstance(raw, str) else raw
                scene_entry["effect"] = {
                    "effect_class": effect_state["effect_class"],
                    "params": params,
                }

            # Placements
            placements = await db.load_scene_placements(scene_id)
            if placements:
                placements_doc: dict[str, Any] = {}
                for p in placements:
                    dev_name = id_to_name.get(p["device_id"], p["device_id"])
                    p_entry: dict[str, Any] = {}
                    pos_keys = ("position_x", "position_y", "position_z")
                    if all(p.get(k) is not None for k in pos_keys):
                        p_entry["position"] = [p["position_x"], p["position_y"], p["position_z"]]
                    if p.get("geometry_type"):
                        p_entry["geometry"] = p["geometry_type"]
                    dir_keys = ("direction_x", "direction_y", "direction_z")
                    if all(p.get(k) is not None for k in dir_keys):
                        p_entry["direction"] = [
                            p["direction_x"],
                            p["direction_y"],
                            p["direction_z"],
                        ]
                    if p.get("length") is not None:
                        p_entry["length"] = p["length"]
                    if p.get("width") is not None:
                        p_entry["width"] = p["width"]
                    if p.get("rows") is not None:
                        p_entry["rows"] = p["rows"]
                    if p.get("cols") is not None:
                        p_entry["cols"] = p["cols"]
                    placements_doc[dev_name] = p_entry
                scene_entry["placements"] = placements_doc

            scenes_doc[scene_id] = scene_entry
        doc["scenes"] = scenes_doc

    # --- Groups ---
    groups = await db.load_groups()
    device_groups = await db.load_device_groups()
    if groups:
        groups_doc: dict[str, Any] = {}
        for group in groups:
            gname = group["name"]
            groups_doc[gname] = {
                "color": group["color"],
                "members": device_groups.get(gname, []),
            }
        doc["groups"] = groups_doc

    # --- Presets ---
    presets = await db.load_presets()
    if presets:
        presets_doc: dict[str, Any] = {}
        for preset in presets:
            raw_params = preset["params"]
            params = json.loads(raw_params) if isinstance(raw_params, str) else raw_params
            presets_doc[preset["name"]] = {
                "effect_class": preset["effect_class"],
                "params": params,
            }
        doc["presets"] = presets_doc

    doc.update(await _export_zones_and_looks(db))
    return tomli_w.dumps(doc)


async def import_toml(db: StateDB, toml_str: str) -> None:
    """Import structured TOML into DB, merging with existing state."""
    data = tomllib.loads(toml_str)

    # --- Config ---
    config_data = data.get("config", {})
    for section, kv in config_data.items():
        if isinstance(kv, dict):
            # Convert all values to JSON-serialized strings for storage
            # Using json.dumps preserves type fidelity: booleans -> "true"/"false",
            # numbers stay numeric strings, strings get quoted then stripped by load_all_config
            str_kv = {k: json.dumps(v) for k, v in kv.items()}
            await db.save_config_bulk(section, str_kv)
            logger.debug(
                "import_toml: imported {} config keys for section '{}'",
                len(str_kv),
                section,
            )

    # --- Devices ---
    devices_data = data.get("devices", {})
    for name, dinfo in devices_data.items():
        if not isinstance(dinfo, dict):
            continue
        backend = dinfo.get("backend", "unknown")
        mac = dinfo.get("mac", "")
        device_id = dinfo.get("device_id", "")
        # Build stable_id: prefer mac, then device_id, then slugified name
        if mac:
            stable_id = f"{backend}:{mac}"
        elif device_id:
            stable_id = f"{backend}:{device_id}"
        else:
            stable_id = f"{backend}:{name.lower().replace(' ', '_')}"

        device_record: dict[str, Any] = {
            "id": stable_id,
            "name": name,
            "backend": backend,
        }
        if "led_count" in dinfo:
            device_record["led_count"] = dinfo["led_count"]
        if "ip" in dinfo:
            device_record["ip"] = dinfo["ip"]
        if "mac" in dinfo:
            device_record["mac"] = dinfo["mac"]
        if "device_id" in dinfo:
            device_record["device_id"] = dinfo["device_id"]
        if "sku" in dinfo:
            device_record["sku"] = dinfo["sku"]
        if "last_latency_ms" in dinfo:
            device_record["last_latency_ms"] = dinfo["last_latency_ms"]

        await db.upsert_device(device_record)
        logger.debug("import_toml: upserted device '{}' ({})", name, stable_id)

    # Build name -> device_id map for placement resolution (after device import)
    all_devices = await db.load_devices()
    name_to_id = {d["name"]: d["id"] for d in all_devices}

    # --- Scenes ---
    scenes_data = data.get("scenes", {})
    for scene_id, sinfo in scenes_data.items():
        if not isinstance(sinfo, dict):
            continue
        scene_record: dict[str, Any] = {
            "id": scene_id,
            "name": sinfo.get("name", scene_id),
        }
        if "mapping_type" in sinfo:
            scene_record["mapping_type"] = sinfo["mapping_type"]
        if "effect_mode" in sinfo:
            scene_record["effect_mode"] = sinfo["effect_mode"]
        if "is_active" in sinfo:
            scene_record["is_active"] = 1 if sinfo["is_active"] else 0
        if "mapping_params" in sinfo:
            mp = sinfo["mapping_params"]
            scene_record["mapping_params"] = json.dumps(mp) if not isinstance(mp, str) else mp
        if "effect_source" in sinfo:
            scene_record["effect_source"] = sinfo["effect_source"]

        await db.save_scene(scene_record)
        logger.debug("import_toml: saved scene '{}'", scene_id)

        # Effect state
        effect_info = sinfo.get("effect", {})
        if effect_info and "effect_class" in effect_info:
            params = effect_info.get("params", {})
            params_str = json.dumps(params)
            await db.save_scene_effect_state(scene_id, effect_info["effect_class"], params_str)

        # Placements
        placements_data = sinfo.get("placements", {})
        for dev_name, pinfo in placements_data.items():
            if not isinstance(pinfo, dict):
                continue
            device_id = name_to_id.get(dev_name, dev_name)
            placement_record: dict[str, Any] = {
                "scene_id": scene_id,
                "device_id": device_id,
            }
            pos = pinfo.get("position")
            if pos and len(pos) == 3:
                placement_record["position_x"] = pos[0]
                placement_record["position_y"] = pos[1]
                placement_record["position_z"] = pos[2]
            if "geometry" in pinfo:
                placement_record["geometry_type"] = pinfo["geometry"]
            direction = pinfo.get("direction")
            if direction and len(direction) == 3:
                placement_record["direction_x"] = direction[0]
                placement_record["direction_y"] = direction[1]
                placement_record["direction_z"] = direction[2]
            if "length" in pinfo:
                placement_record["length"] = pinfo["length"]
            if "width" in pinfo:
                placement_record["width"] = pinfo["width"]
            if "rows" in pinfo:
                placement_record["rows"] = pinfo["rows"]
            if "cols" in pinfo:
                placement_record["cols"] = pinfo["cols"]

            await db.save_placement(placement_record)

    # --- Groups ---
    groups_data = data.get("groups", {})
    for gname, ginfo in groups_data.items():
        if not isinstance(ginfo, dict):
            continue
        color = ginfo.get("color", "#888888")
        await db.save_group(gname, color)
        for member_id in ginfo.get("members", []):
            await db.assign_device_group(gname, member_id)

    # --- Presets ---
    presets_data = data.get("presets", {})
    for preset_name, pinfo in presets_data.items():
        if not isinstance(pinfo, dict):
            continue
        effect_class = pinfo.get("effect_class", "")
        params = pinfo.get("params", {})
        params_str = json.dumps(params)
        await db.save_preset(preset_name, effect_class, params_str)
        logger.debug("import_toml: saved preset '{}'", preset_name)

    await _import_zones_and_looks(db, data)


async def _export_zones_and_looks(db: StateDB) -> dict[str, Any]:
    """Zones, saved looks, stars and what each zone runs (M1)."""
    store = ZoneStore(db)
    doc: dict[str, Any] = {}
    zones = await store.load_zones()
    if zones:
        doc["zones"] = {
            zone.id: {
                "name": zone.name,
                "kind": zone.kind,
                "all_lights": zone.all_lights,
                "lights": list(zone.lights),
            }
            for zone in zones
        }
    looks = await db.fetch_all(
        "SELECT id, body, created_at, updated_at FROM looks ORDER BY created_at, id"
    )
    if looks:
        doc["looks"] = {
            look_id: {"body": body, "created_at": created_at, "updated_at": updated_at}
            for look_id, body, created_at, updated_at in looks
        }
    stars = await db.fetch_all("SELECT look_id FROM look_stars ORDER BY look_id")
    if stars:
        doc["stars"] = {"looks": [look_id for (look_id,) in stars]}
    assignments = await store.load_assignments()
    if assignments:
        doc["running"] = {
            a.zone_id: {
                "look_id": a.look_id,
                "look": a.look_json,
                "brightness": a.brightness,
                "lights": list(a.lights),
                "started_at": a.started_at,
            }
            for a in assignments
        }
    return doc


def _tables(data: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    """The sub-tables of a top-level table; anything else there is ignored."""
    table = data.get(key, {})
    if not isinstance(table, dict):
        return {}
    return {name: value for name, value in table.items() if isinstance(value, dict)}


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _zone(zone_id: str, info: dict[str, Any]) -> ZoneRecord:
    kind = info.get("kind", "group")
    if kind not in get_args(ZoneKind):
        logger.warning("import_toml: zone '{}' has unknown kind {!r}; using group", zone_id, kind)
        kind = "group"
    return ZoneRecord(
        id=zone_id,
        name=str(info.get("name", zone_id)),
        kind=cast(ZoneKind, kind),
        lights=_strings(info.get("lights")),
        all_lights=bool(info.get("all_lights", False)),
    )


def _assignment(zone_id: str, info: dict[str, Any]) -> Assignment | None:
    look_id, look = info.get("look_id"), info.get("look")
    brightness, started_at = info.get("brightness", 1.0), info.get("started_at")
    if (
        not isinstance(look_id, str)
        or not isinstance(look, str)
        or not isinstance(brightness, int | float)
        or isinstance(brightness, bool)
        or not isinstance(started_at, datetime)
    ):
        return None
    return Assignment(
        zone_id=zone_id,
        look_id=look_id,
        look_json=look,
        brightness=clamp01(float(brightness)),
        lights=_strings(info.get("lights")),
        started_at=as_utc(started_at),
    )


async def _import_zones_and_looks(db: StateDB, data: dict[str, Any]) -> None:
    store = ZoneStore(db)
    for zone_id, info in _tables(data, "zones").items():
        await store.save_zone(_zone(zone_id, info))

    built_in = {look.id for look in builtin_looks()}
    now = utcnow().isoformat()
    for look_id, info in _tables(data, "looks").items():
        body = info.get("body")
        if look_id in built_in or not isinstance(body, str):
            logger.warning("import_toml: skipped look '{}' (built in, or no body)", look_id)
            continue
        created_at = str(info.get("created_at", now))
        await db.write(UPSERT_LOOK, (look_id, body, created_at, str(info.get("updated_at", now))))

    stars = data.get("stars", {})
    starred = _strings(stars.get("looks") if isinstance(stars, dict) else None)
    await db.write_many([(STAR_LOOK, (look_id,)) for look_id in starred])

    known = {zone.id for zone in await store.load_zones()}
    for zone_id, info in _tables(data, "running").items():
        assignment = _assignment(zone_id, info) if zone_id in known else None
        if assignment is None:
            logger.warning("import_toml: skipped what zone '{}' was running", zone_id)
            continue
        await store.save_assignment(assignment)


# --- First-Launch Migration ---


async def migrate_from_toml(
    db: StateDB,
    config_path: Path | None = None,
    presets_path: Path | None = None,
) -> None:
    """Migrate legacy TOML files into the DB on first launch.

    For each provided path:
    - If the file exists, parse it, import data into DB, rename to .bak (or leave it,
      with a warning, when it can't be renamed).
    - If the file does not exist, silently skip.

    config_path format (old config.toml):
      [engine]           — engine config
      [network]          — network config
      [web]              — web config
      [effect]           — active_effect + per-effect param sub-tables
      Migrates engine/network/web config keys and creates a "default" scene
      with the active effect state.

    presets_path format (old presets.toml):
      [presets."<name>"]
      effect_class = "..."
      params = { ... }
    """
    if config_path is not None and config_path.exists():
        await _migrate_config_toml(db, config_path)
        _set_aside(config_path)

    if presets_path is not None and presets_path.exists():
        await _migrate_presets_toml(db, presets_path)
        _set_aside(presets_path)


def _set_aside(path: Path) -> None:
    """Rename a migrated file to .bak. A file that can't be renamed (config.toml is mounted
    read-only in the container) stays where it is: the database is the source of truth."""
    bak = path.with_suffix(".toml.bak")
    try:
        path.rename(bak)
    except OSError as exc:
        logger.warning("migrate_from_toml: left {} in place ({})", path, exc)
        return
    logger.info("migrate_from_toml: migrated {}, backed up to {}", path, bak)


async def _migrate_config_toml(db: StateDB, path: Path) -> None:
    """Parse old config.toml and import into DB."""
    raw = tomllib.loads(path.read_text())

    # Config sections to migrate directly (key-value, with nested sub-tables flattened)
    _PLAIN_SECTIONS = ("engine", "network", "web", "discovery", "devices")
    for section in _PLAIN_SECTIONS:
        if section not in raw or not isinstance(raw[section], dict):
            continue
        # Top-level keys (non-dict values), as JSON like every other config write
        str_kv = {k: json.dumps(v) for k, v in raw[section].items() if not isinstance(v, dict)}
        if str_kv:
            await db.save_config_bulk(section, str_kv)
        # Nested sub-tables: flatten as dotted section keys, e.g. "devices.lifx"
        for sub_key, sub_val in raw[section].items():
            if isinstance(sub_val, dict):
                nested_section = f"{section}.{sub_key}"
                nested_kv = {
                    k: json.dumps(v) for k, v in sub_val.items() if not isinstance(v, dict)
                }
                if nested_kv:
                    await db.save_config_bulk(nested_section, nested_kv)

    # Effect config → "default" scene + scene_effect_state
    effect_cfg = raw.get("effect", {})
    if effect_cfg:
        active_effect = effect_cfg.get("active_effect", "")
        if active_effect:
            # Per-effect params are stored as sub-tables: effect.<effect_name> = { ... }
            params: dict[str, Any] = {}
            effect_params_table = effect_cfg.get(active_effect, {})
            if isinstance(effect_params_table, dict):
                params = effect_params_table

            # Create the "default" scene if it doesn't already exist
            existing_scenes = await db.load_scenes()
            if not any(s["id"] == "default" for s in existing_scenes):
                await db.save_scene(
                    {
                        "id": "default",
                        "name": "Default",
                        "mapping_type": "linear",
                        "effect_mode": "independent",
                        "is_active": 1,
                    }
                )

            await db.save_scene_effect_state(
                "default",
                active_effect,
                json.dumps(params),
            )
            logger.debug(
                "migrate_from_toml: created default scene with effect '{}', params={}",
                active_effect,
                params,
            )


async def _migrate_presets_toml(db: StateDB, path: Path) -> None:
    """Parse old presets.toml and import presets into DB."""
    raw = tomllib.loads(path.read_text())
    presets_table = raw.get("presets", {})
    for preset_name, pinfo in presets_table.items():
        if not isinstance(pinfo, dict):
            continue
        effect_class = pinfo.get("effect_class", "")
        params = pinfo.get("params", {})
        params_str = json.dumps(params)
        await db.save_preset(preset_name, effect_class, params_str)
        logger.debug("migrate_from_toml: migrated preset '{}'", preset_name)


async def save_config_to_db(config: AppConfig, state_db: StateDB) -> None:
    """Persist AppConfig to StateDB config table.

    Shared helper used by main startup and the config router when config is
    updated at runtime.
    """

    def _str_dict(obj: object) -> dict[str, str]:
        return {k: json.dumps(v) for k, v in dataclasses.asdict(obj).items()}  # type: ignore[call-overload]

    await state_db.save_config_bulk("engine", _str_dict(config.engine))
    await state_db.save_config_bulk("network", _str_dict(config.network))
    await state_db.save_config_bulk("web", _str_dict(config.web))
    await state_db.save_config_bulk("discovery", _str_dict(config.discovery))

    effect_plain = {
        k: v
        for k, v in dataclasses.asdict(config.effect).items()
        if not isinstance(v, (dict, list))
    }
    await state_db.save_config_bulk("effect", {k: json.dumps(v) for k, v in effect_plain.items()})

    logger.debug("Config saved to StateDB")
