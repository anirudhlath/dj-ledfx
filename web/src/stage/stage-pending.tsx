/** The stage's place while its code or its data loads: the stage's own background, so nothing jumps. */
export function StagePending() {
  return <section aria-label="Home, live" aria-busy="true" className="size-full bg-bg" />
}
