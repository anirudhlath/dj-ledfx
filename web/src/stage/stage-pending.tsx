/** The stage's name, for assistive technology: the section it draws in, and its place while it loads. */
export const STAGE_LABEL = 'Home, live'

/** The stage's place while its code or its data loads: the stage's own background, so nothing jumps. */
export function StagePending() {
  return <section aria-label={STAGE_LABEL} aria-busy="true" className="size-full bg-bg" />
}
