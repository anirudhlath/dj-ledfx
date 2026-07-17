# Resolve conflict payload to display names server-side

**Summary:** POST /api/scenes/{id}/activate returns conflicting_devices as stable_ids; the frontend grew DeviceResponse.stable_id + devices plumbing in useScenes solely to map ids to names for one toast. Project convention: the web layer resolves names. The route has device_manager in hand.

**Acceptance criteria:** Conflict payload includes display names (keep stable_ids for machine use); useScenes drops its devices param; DeviceResponse.stable_id retained only if another consumer needs it.
