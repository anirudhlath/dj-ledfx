import { createElement, memo, type ComponentType } from 'react'

/** How often each counted component rendered since the last resetRenders(). */
export const renders: Record<string, number> = {}

export function resetRenders(): void {
  for (const name of Object.keys(renders)) delete renders[name]
}

/** What React.memo() makes: the component it wraps, and its comparison. */
interface Memoised<P> {
  $$typeof: symbol
  type: ComponentType<P>
  compare: ((before: P, after: P) => boolean) | null
}

const isMemo = <P>(component: unknown): component is Memoised<P> =>
  (component as Partial<Memoised<P>>).$$typeof === Symbol.for('react.memo')

/**
 * `Real`, counting each render under `name`. For a vi.mock factory. A memoised component stays
 * memoised, so a render that memo() skips isn't counted.
 */
export function counted<P extends object>(name: string, Real: ComponentType<P>): ComponentType<P> {
  const inner = isMemo<P>(Real) ? Real.type : Real
  function Counted(props: P) {
    renders[name] = (renders[name] ?? 0) + 1
    return createElement(inner, props)
  }
  return isMemo<P>(Real) ? (memo(Counted, Real.compare ?? undefined) as unknown as ComponentType<P>) : Counted
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
