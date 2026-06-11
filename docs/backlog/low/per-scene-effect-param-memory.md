# Remember per-effect params when switching effects on a scene deck

**Summary:** Switching a scene's effect sends empty params, so returning to a previously tuned effect gets defaults. Same behavior as the global deck; per-scene preset save (spec'd out of scope 2026-06-11) would cover this.

**Acceptance criteria:** Switching back to an effect previously used on the same scene restores its last params (client-side memory or server-side per-effect state).
