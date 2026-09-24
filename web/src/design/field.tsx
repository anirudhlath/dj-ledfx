import { useId, type ComponentPropsWithoutRef } from 'react'
import { cx } from './cx'

export interface FieldProps extends Omit<ComponentPropsWithoutRef<'input'>, 'id' | 'className'> {
  label: string
  /** A unit suffix, e.g. "m" or "ms". */
  unit?: string
  className?: string
}

/** §6.1 Field: a label above a 32 px box holding a mono value and an optional unit. */
export function Field({ label, unit, className, ...input }: FieldProps) {
  const id = useId()
  return (
    <div className={cx('flex flex-col gap-1.25', className)}>
      <label htmlFor={id} className="text-[11.5px] font-medium text-text-3">
        {label}
      </label>
      <div className="flex h-8 items-center gap-1.5 rounded-control border border-line bg-control px-2.5 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-text">
        <input id={id} className="num min-w-0 flex-1 bg-transparent text-size-control text-text outline-none" {...input} />
        {unit && <span className="text-meta text-text-3">{unit}</span>}
      </div>
    </div>
  )
}
