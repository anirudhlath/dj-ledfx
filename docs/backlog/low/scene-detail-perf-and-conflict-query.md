# SceneDetail/activation query efficiency

**Summary:** GET /api/scenes/{id} builds a transient SceneModel+SpatialCompositor per request (O(N) numpy); activation conflict detection issues O(active scenes × placements) sequential DB reads. Both fine at current scale (2-5 scenes, ~10 devices) — revisit if scene counts grow or a WS scene channel starts hammering these paths.

**Acceptance criteria:** Serve strip indices from the live pipeline's compositor when the scene is active; replace the conflict loop with a single SQL set-intersection query.
