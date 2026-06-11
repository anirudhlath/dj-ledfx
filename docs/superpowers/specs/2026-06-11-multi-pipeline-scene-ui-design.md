# Multi-Pipeline Scene Management UI — Design

**Date:** 2026-06-11
**Status:** Approved for implementation (autonomous session; requirements sourced from
`up_next_frontend_multi_pipeline` memory captured with the user on 2026-03-24)

## Problem

The backend supports multi-pipeline rendering (PR #8): scenes activate/deactivate
independently, each active scene gets its own `ScenePipeline` (deck, ring buffer,
compositor), and a default pipeline catches unassigned devices. The frontend exposes
none of it — the Scene page edits only the legacy single TOML scene, and the Live page
drives only the global/default effect deck.

Exploration also surfaced three backend defects that make the feature broken end-to-end
even with a UI on top:

1. **Per-scene effect state is persisted but never restored.**
   `PipelineManager._build_deck_for_scene` (`spatial/pipeline_manager.py:312`) always
   returns `EffectDeck(BeatPulse())` despite its docstring and despite
   `scene_effect_state` rows being written on every `set_scene_effect`.
2. **Multi-scene compositing is keyed inconsistently.** `_build_pipeline` keys the
   in-memory `SceneModel` placements by DB `device_id` (= `stable_id`,
   `pipeline_manager.py:252`), but the scheduler hot path composites by
   `device_info.name` (`scheduling/scheduler.py:325`). For any device with a real
   `stable_id` (all LIFX/Govee hardware), `composite()` returns `None` and the device
   receives the raw uncomposited strip.
3. **Activating an already-active scene returns HTTP 500.**
   `PipelineManager.activate_scene` raises `ValueError` (`pipeline_manager.py:115`)
   which `POST /api/scenes/{id}/activate` does not catch (`web/router_scene.py:425`).

And two API gaps that block the UI:

4. **No endpoint returns a scene's placements** — `PUT/DELETE
   /api/scenes/{id}/devices/{name}` exist but there is no read, so a scene editor
   cannot display what it is editing.
5. **`UpdateSceneRequest` has no `mapping_params`** — the `scenes.mapping_params` DB
   column is unreachable from the API, so radial center/radius (and linear axis) can't
   be edited per scene.

## Approaches Considered

- **A. Frontend-only minimal** (the four points from the memory verbatim): scene list +
  activate/deactivate + per-scene effect picker. Rejected: without a placement read
  endpoint users can create scenes but never see or edit their contents, and the three
  backend defects above mean activated scenes render wrong and lose their effects on
  restart. The feature would demo but not work.
- **B. Full integration (chosen)**: fix the three defects, fill the two API gaps, then
  build the UI — scene management panel in the Scene editor, parameterized 3D editor,
  per-scene effect tabs on the Live page.
- **C. B plus live pipeline hot-rebuild, per-scene preset save, per-device pipeline
  badges.** Rejected (YAGNI): a deactivate→activate cycle already rebuilds a pipeline;
  preset *load* covers the per-scene use case; badges add API surface for cosmetics.

## Design (Approach B)

### Backend changes

All in existing files; no new modules.

1. **Effect restore** — `activate_scene` and `load_active_scenes` load
   `scene_effect_state` via `StateDB.load_scene_effect_state(scene_id)` and pass the
   row into `_build_pipeline` → `_build_deck_for_scene(scene_id, effect_row)`. The deck
   is built with the persisted effect via the effects registry (`create`); unknown
   effect class or bad params logs a warning and falls back to `BeatPulse`. Shared-mode
   decks keep current behavior (one shared deck; restore is out of scope for shared).
2. **Compositor key fix** — `_build_pipeline` keys `scene_placements` (and
   `DevicePlacement.device_id`) by `managed.adapter.device_info.name` instead of the DB
   `stable_id`, matching what the scheduler passes to `composite()`. DB rows keep
   `stable_id`; only the in-memory model uses names. (Scheduler hot path stays
   untouched — no extra lookups at 60 fps.)
3. **Idempotent activate** — add `PipelineManager.is_scene_active(scene_id) -> bool`.
   The activate route returns `200 {"status": "already_active"}` when set, and catches
   remaining `ValueError`s from `activate_scene` as `409` (build failure, missing
   scene). The existing `409 device_conflict` payload is unchanged.
4. **Scene detail** — `GET /api/scenes/{scene_id}` response grows from `SceneListItem`
   to `SceneDetail(SceneListItem)` adding `placements: list[PlacementResponse]` and
   `mapping: MappingResponse | None`. Placement `device_id` is the resolved **display
   name** (via `DeviceManager.get_by_stable_id`, falling back to the raw stable_id for
   unknown devices) so the response shape matches the legacy `GET /api/scene` contract
   that the 3D editor, WS frame names, and the per-scene `PUT/DELETE .../devices/{name}`
   routes already use. `strip_index` is computed from a transient
   `SceneModel`+mapping built from the DB rows (same construction as
   `_build_pipeline`).
5. **Mapping params** — `UpdateSceneRequest.mapping_params: dict[str, Any] | None`;
   the PUT route persists it to `scenes.mapping_params` (JSON).
6. **`DeviceResponse.stable_id`** — expose `effective_id` so the frontend can map
   `conflicting_devices` stable_ids to display names in error toasts.

Pipeline rebuild semantics are unchanged: placement/mapping edits are DB-only and take
effect at next activation. The **frontend** owns re-applying: after a successful
placement/mapping/effect-mode mutation on an *active* scene it calls
deactivate→activate ("re-apply") and reports it in the toast.

### Frontend changes

**Types & client** (`lib/types.ts`, `lib/api-client.ts`): `SceneListItem`,
`SceneDetail` types; methods `listScenes`, `createScene`, `updateScene`, `deleteScene`,
`activateScene`, `deactivateScene`, `getSceneDetail`, `getSceneEffect`,
`setSceneEffect`, `updateScenePlacement`, `deleteScenePlacement`. `activateScene`
throws a structured error carrying `conflicting_devices` when the 409
`device_conflict` payload is present.

**`hooks/use-scenes.ts`** (new): scene list state + CRUD + activate/deactivate.
Conflict errors resolve stable_ids → display names via the devices list and surface via
`toast.error`. Mutations refetch the list (existing mutate-then-refresh convention).

**`hooks/use-scene.ts`** (parameterized): `useScene(sceneId: string | null)` — `null`
keeps today's legacy `/api/scene` behavior (the "Default" TOML scene); a DB id routes
reads to `GET /api/scenes/{id}` and mutations to the per-scene endpoints. Return shape
is unchanged so `SceneViewport`, `DeviceListPanel`, `PropertiesPanel`,
`MappingPreview` keep working as-is. When the edited scene is active, successful
placement/mapping mutations trigger the re-apply cycle.

**Scene page**: new `ScenesPanel` card at the top of the left column (above
`DeviceListPanel`): one row per scene — name, active `Badge`, activate/deactivate
button, delete button — plus a "Default" pseudo-entry (always active, not deletable)
and a create-scene input. Selecting a row switches the 3D editor to that scene.
`PropertiesPanel`/toolbar additions: per-scene `effect_mode` Select (disabled while
active — the backend 409s), rename via the existing inline-input conventions. Existing
compact styling (`Card`, `h-7 text-xs`, `Badge`, sonner toasts).

**Live page**: a `Tabs` strip above the effect deck — "Default" plus one tab per
*active* scene (from `useScenes`). The Default tab keeps today's `use-effects`
(global deck + presets). Scene tabs drive `GET/PUT /api/scenes/{id}/effect` with the
same param-editor UI (schema catalog from `GET /api/effects` is shared); preset *load*
applies the preset's effect+params through the scene PUT client-side; preset *save*
stays Default-only. The 3D preview viewport shows the selected tab's scene placements
(Default tab → legacy scene, as today).

**Deviation from the memory spec:** point 3 said "pass `scene_id` in WS `set_effect`".
The frontend currently performs all effect mutations over REST (`PUT
/api/effects/active`), and the per-scene REST endpoint provides identical behavior with
response-based error handling. We keep REST for consistency; the WS path stays
backend-supported and tested.

### Error handling

- `409 device_conflict` → toast listing conflicting device display names.
- `409` effect_mode-while-active → prevented in UI (control disabled), toast as backstop.
- `404` scene effect on inactive scene → UI only renders effect controls for active
  scenes, so this is unreachable in normal flow.
- `503` (no DB) → `fetchJson` throw → toast; ScenesPanel renders an empty state.

### Testing

Backend (pytest, sync `TestClient` per existing convention):
- `GET /api/scenes/{id}` detail: placements with resolved names, mapping payload,
  strip_index presence; unknown-device fallback to stable_id.
- `PUT /api/scenes/{id}` persists `mapping_params`.
- Activate: already-active → 200 `already_active`; `activate_scene` ValueError → 409;
  device-conflict regression stays green; **atomicity** — when `pm.activate_scene`
  raises, the DB `is_active` flag stays 0 (covers the CLAUDE.md invariant, currently
  untested).
- PipelineManager: effect restored on activation from `scene_effect_state`
  (and on `load_active_scenes`); unknown effect class falls back to BeatPulse;
  compositor placements keyed by device *name* when `stable_id` differs.
- `DeviceResponse.stable_id` presence.

Frontend: `npx tsc --noEmit` and `npm run build` (no unit-test harness exists; manual
flows go to `docs/qa-backlog/`).

## Out of Scope

- Per-scene preset save; shared-mode effect restore; live hot-rebuild endpoint;
  per-device pipeline badges on DeviceMonitor; migrating the legacy TOML scene into the
  DB; WS-driven effect mutations from the frontend.
