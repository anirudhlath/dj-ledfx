"""TOML import/export marshaling for StateDB.

Export format:
  [config.<section>]          — config key-value pairs
  [devices."<name>"]          — device records keyed by display name
  [scenes."<id>"]             — scene records
  [scenes."<id>".effect]      — scene effect state
  [scenes."<id>".placements."<device_name>"]  — device placements
  [groups."<name>"]           — group metadata + members
  [presets."<name>"]          — preset records
"""

from __future__ import annotations

import dataclasses
import json
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any

import tomli_w
from loguru import logger

from dj_ledfx.persistence.state_db import StateDB

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


# --- First-Launch Migration ---


async def migrate_from_toml(
    db: StateDB,
    config_path: Path | None = None,
    presets_path: Path | None = None,
) -> None:
    """Migrate legacy TOML files into the DB on first launch.

    For each provided path:
    - If the file exists, parse it, import data into DB, rename to .bak.
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
        bak = config_path.with_suffix(".toml.bak")
        config_path.rename(bak)
        logger.info("migrate_from_toml: migrated config, backed up to {}", bak)

    if presets_path is not None and presets_path.exists():
        await _migrate_presets_toml(db, presets_path)
        bak = presets_path.with_suffix(".toml.bak")
        presets_path.rename(bak)
        logger.info("migrate_from_toml: migrated presets, backed up to {}", bak)


async def _migrate_config_toml(db: StateDB, path: Path) -> None:
    """Parse old config.toml and import into DB."""
    raw = tomllib.loads(path.read_text())

    # Config sections to migrate directly (key-value, with nested sub-tables flattened)
    _PLAIN_SECTIONS = ("engine", "network", "web", "discovery", "devices")
    for section in _PLAIN_SECTIONS:
        if section not in raw or not isinstance(raw[section], dict):
            continue
        # Top-level keys (non-dict values)
        str_kv = {k: str(v) for k, v in raw[section].items() if not isinstance(v, dict)}
        if str_kv:
            await db.save_config_bulk(section, str_kv)
        # Nested sub-tables: flatten as dotted section keys, e.g. "devices.lifx"
        for sub_key, sub_val in raw[section].items():
            if isinstance(sub_val, dict):
                nested_section = f"{section}.{sub_key}"
                nested_kv = {k: str(v) for k, v in sub_val.items() if not isinstance(v, dict)}
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
