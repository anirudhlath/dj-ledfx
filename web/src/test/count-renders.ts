import { createElement, type ComponentType } from 'react'

/** How often each counted component rendered since the last resetRenders(). */
export const renders: Record<string, number> = {}

export function resetRenders(): void {
  for (const name of Object.keys(renders)) delete renders[name]
}

/** `Real`, counting each render under `name`. For a vi.mock factory. */
export function counted<P extends object>(name: string, Real: ComponentType<P>): ComponentType<P> {
  function Counted(props: P) {
    renders[name] = (renders[name] ?? 0) + 1
    return createElement(Real, props)
  }
  return Counted
}

/**
 * A vi.mock factory: the module as it is, but its component `exportName` counted under `name`. The
 * factory runs before the test file's imports, so reach this through vi.hoisted.
 */
export function countedExport(name: string, exportName: string) {
  return async (importOriginal: <T>() => Promise<T>) => {
    const real = await importOriginal<Record<string, ComponentType<object>>>()
    return { ...real, [exportName]: counted(name, real[exportName]) }
  }
}
