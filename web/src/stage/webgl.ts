// The stage draws with WebGL 2 (three.js needs it). A browser without it, or with it switched off,
// gets the no-WebGL stand-in instead of a blank box. Asking makes a WebGL context and drops it again,
// so a page asks once, not on every visit to Live.
let answer: boolean | undefined

export function hasWebGL2(): boolean {
  answer ??= probe()
  return answer
}

function probe(): boolean {
  // jsdom has none, and asking its canvas for a context logs an error.
  if (typeof WebGL2RenderingContext === 'undefined') return false
  try {
    const gl = document.createElement('canvas').getContext('webgl2')
    // Browsers keep only a few contexts alive: let this one go at once.
    gl?.getExtension('WEBGL_lose_context')?.loseContext()
    return gl !== null
  } catch {
    return false
  }
}
