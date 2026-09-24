/**
 * The router's basename, from Vite's base ("/next/"). React Router matches a bare /next only
 * against "/next", never "/next/", and FastAPI serves the app at a bare /next too.
 */
export function routerBasename(base: string): string {
  return base.replace(/\/$/, '') || '/'
}
