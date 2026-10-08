// The browser's localStorage, for per-viewer conveniences: the stage's view (§7.2) and the composer's
// last zone (§8.2). A storage that is missing, full or blocked only costs what it would remember.

/** localStorage, or null where reaching it throws (a sandboxed frame, blocked site data). */
export function browserStorage(): Storage | null {
  try {
    return window.localStorage
  } catch {
    return null
  }
}
