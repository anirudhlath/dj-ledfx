# Migrate TOML scene_config placements into the default scene

**Summary:** `toml_io.migrate_from_toml` creates the "default" scene and migrates the active effect, but ignores `scene_config.devices` — the user's existing 3D placements (8 devices in config.toml) never reach `scene_placements`, so the migrated default scene is empty in the editor and the Live preview.

**Context:** Found 2026-06-11 while running the demo after the scene-management-UI branch. The web layer also receives `scene_model=None` and a `None` default compositor in `main.py`, so the legacy in-memory scene path is empty too. Workaround: place devices manually in the new per-scene 3D editor (placements then persist to the DB properly).

**Acceptance criteria:**
- `migrate_from_toml` writes `scene_placements` rows for `scene_config.devices` (resolving display names → stable_ids via the DB devices table), including geometry/direction/length and mapping_type/mapping_params.
- A one-shot repair path exists for DBs that already migrated without placements (e.g. re-import via POST /api/state/import or a small migration).
- Demo run shows the migrated placements in the scene editor without manual re-placement.
