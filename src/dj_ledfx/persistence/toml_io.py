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

import json
import tomllib
from typing import Any

import tomli_w
from loguru import logger

from dj_ledfx.persistence.state_db import StateDB

# Config sections that belong at the top level (not per-device, not internal)
_EXPORTABLE_CONFIG_SECTIONS = {
    "engine",
    "network",
    "web",
    "devices",
    "discovery",
}

# Internal section used for schema version tracking
_META_SECTION = "_meta"


async def export_toml(db: StateDB) -> str:
    """Export entire DB state as structured TOML string."""
    doc: dict[str, Any] = {}

    # --- Config ---
    # Load all config rows by querying the raw table directly
    all_config_rows = await db._execute_read(
        "SELECT section, key, value FROM config WHERE section != ?",
        (_META_SECTION,),
    )
    config_by_section: dict[str, dict[str, str]] = {}
    for section, key, value in all_config_rows:
        config_by_section.setdefault(section, {})[key] = value

    if config_by_section:
        doc["config"] = config_by_section

    # --- Devices ---
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

            # Effect state
            effect_state = await db.load_scene_effect_state(scene_id)
            if effect_state:
                raw = effect_state["params"]
                params = json.loads(raw) if isinstance(raw, str) else raw
                scene_entry["effect"] = {
                    "effect_class": effect_state["effect_class"],
                    "params": params,
                }

            # Placements — build name lookup for devices
            placements = await db.load_scene_placements(scene_id)
            if placements:
                # Build device_id -> name map
                all_devices = await db.load_devices()
                id_to_name = {d["id"]: d["name"] for d in all_devices}

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
            # Convert all values to strings for storage
            str_kv = {k: str(v) for k, v in kv.items()}
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
