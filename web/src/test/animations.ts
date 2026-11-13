// jsdom has no Web Animations, so an element has no getAnimations(). In a browser a look thumb's motif
// has CSS animations, which the thumb writer reads once and seeks; this stands in for two of them.

/** What the thumb writer touches of an animation. */
export interface StubAnimation {
  currentTime: number | null
}

/**
 * Stubs `element.getAnimations()` with two animations, never seeked (`currentTime` null), and returns them.
 * They are the same objects on every call, as a browser hands back the same animations.
 */
export function stubAnimations(element: Element): StubAnimation[] {
  const animations: StubAnimation[] = [{ currentTime: null }, { currentTime: null }]
  element.getAnimations = () => animations as unknown as Animation[]
  return animations
}
