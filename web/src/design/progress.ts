// A ProgressBar's value, and its move from an animation frame without React (F3 decision 17).

/** 0–1 as a whole percent, clamped. */
export const percentOf = (value: number): number => Math.round(Math.min(Math.max(value, 0), 1) * 100)

/** Moves a ProgressBar from an animation frame, its fill and its value both, without React. */
export function writeProgress(bar: HTMLElement, value: number): void {
  const percent = String(percentOf(value))
  if (bar.getAttribute('aria-valuenow') === percent) return
  bar.setAttribute('aria-valuenow', percent)
  ;(bar.firstElementChild as HTMLElement).style.width = `${percent}%`
}
