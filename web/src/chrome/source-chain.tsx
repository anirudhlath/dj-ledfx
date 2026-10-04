// §6.7 SourceChain: Pro DJ Link → Music → Internal, the active source inverted, each with its status
// (§8.8, F3 decision 7). Inputs.html draws it as a row; the tempo source popover stacks it.
import { Fragment } from 'react'
import type { TempoSource } from '@/api/contract'
import { cx } from '@/design/cx'
import { Icon } from '@/design/icon'
import { TEMPO_SOURCES } from './sources'

const ORDER = Object.keys(TEMPO_SOURCES) as TempoSource[]

export interface SourceChainProps {
  active: TempoSource
  statuses: Record<TempoSource, string>
  /** "row": Inputs (F6). "column": the tempo source popover. */
  direction?: 'row' | 'column'
}

export function SourceChain({ active, statuses, direction = 'row' }: SourceChainProps) {
  return (
    <div role="group" aria-label="Where the tempo comes from" className={cx('flex gap-2', direction === 'row' ? 'items-center' : 'flex-col')}>
      {ORDER.map((source, index) => {
        const on = source === active
        return (
          <Fragment key={source}>
            {index > 0 && <Icon name={direction === 'row' ? 'right' : 'down'} size={14} className="shrink-0 self-center text-text-3" />}
            <div
              aria-current={on ? 'true' : undefined}
              className={cx('flex min-w-0 flex-1 items-center gap-2.5 rounded-tile border px-3 py-2.5', on ? 'border-text bg-control' : 'border-line')}
            >
              <Icon name={TEMPO_SOURCES[source].icon} size={18} className={on ? 'text-text' : 'text-text-3'} />
              <span className="flex min-w-0 flex-col gap-0.5">
                <span className={cx('text-size-control font-semibold', on ? 'text-text' : 'text-text-2')}>{TEMPO_SOURCES[source].label}</span>
                <span className={cx('truncate text-[11.5px]', on ? 'text-text-2' : 'text-text-3')}>{statuses[source]}</span>
              </span>
            </div>
          </Fragment>
        )
      })}
    </div>
  )
}
