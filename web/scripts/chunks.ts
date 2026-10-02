// The bundle's named chunks: vite.config.ts makes them, and scripts/check-dist.ts weighs the rest
// against §14's budget.

/** three.js's chunk (`codeSplitting` in vite.config.ts), which §14's budget leaves out. */
export const THREE_CHUNK = 'three'
