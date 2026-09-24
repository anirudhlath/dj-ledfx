/**
 * The dj-ledfx mark, copied from the rail in reference/Main.html (it isn't in icons.ts),
 * with its fixed colour swapped for currentColor.
 */
export function Logo() {
  return (
    <svg width="30" height="30" viewBox="0 0 32 32" aria-hidden="true" focusable="false" className="block shrink-0">
      <path d="M16 3 28 9.5v13L16 29 4 22.5v-13z" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M4 9.5 16 16l12-6.5M16 16v13" fill="none" stroke="currentColor" strokeOpacity="0.35" strokeWidth="1.2" />
      <circle cx="16" cy="16" r="5.5" fill="currentColor" fillOpacity="0.16" />
      <circle cx="16" cy="16" r="2.6" fill="currentColor" />
    </svg>
  )
}
