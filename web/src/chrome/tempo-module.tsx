import { cx } from '@/design/cx'
import { Icon } from '@/design/icon'
import type { IconName } from '@/design/icons'
import { formatBpm } from '@/lib/format'
import type { TempoSource, TempoState } from './state'

export interface TempoModuleProps extends TempoState {
  /** "bar": the desktop top bar. "strip": the phone strip under the header on Live. */
  variant: 'bar' | 'strip'
  onSourceClick?: () => void
  onTap?: () => void
}

const SOURCE: Record<TempoSource, { label: string; icon: IconName }> = {
  prodjlink: { label: 'Pro DJ Link', icon: 'deck' },
  music: { label: 'Music', icon: 'music' },
  internal: { label: 'Internal', icon: 'tempo' },
}

/** §6.2 TempoModule. F0 draws a still beat; F3 drives the pips from the beat clock (§5.4). */
export function TempoModule({ variant, source, bpm, beat, bar, stale, onSourceClick, onTap }: TempoModuleProps) {
  const { label, icon } = SOURCE[source]
  const staleNote = stale && <span className="sr-only">, stale</span>
  const pips = <Pips beat={stale ? null : beat} variant={variant} />

  if (variant === 'strip') {
    return (
      <div
        role="group"
        aria-label="Tempo"
        // At 320 px (the WCAG reflow width) the gaps tighten so TAP stays inside the strip.
        className="flex h-(--phone-tempo-h) items-center gap-3 rounded-card border border-line bg-raised pr-1 pl-3 max-[22.5rem]:gap-2"
      >
        <span className={cx('inline-flex items-center gap-1.5 text-data font-semibold', stale ? 'text-signal' : 'text-text-2')}>
          <Icon name={icon} size={16} />
          {label}
          {staleNote}
        </span>
        <span className="num text-bpm font-semibold tracking-[-0.02em]">
          {formatBpm(bpm)}
          <span className="sr-only"> BPM</span>
        </span>
        {pips}
        <button
          type="button"
          onClick={onTap}
          className="h-10 rounded-[9px] border border-line-strong bg-control-hover px-4 text-size-control font-bold tracking-[0.06em] uppercase"
        >
          Tap
        </button>
      </div>
    )
  }

  return (
    <div
      role="group"
      aria-label="Tempo"
      className="flex h-10 w-95 items-center justify-between gap-3 rounded-tile border border-line bg-raised px-1.5 tablet:w-auto"
    >
      <button
        type="button"
        aria-haspopup="dialog"
        onClick={onSourceClick}
        className={cx('inline-flex h-7 items-center gap-1.5 rounded-chip bg-control px-2 text-meta font-semibold', stale ? 'text-signal' : 'text-text-2')}
      >
        <Icon name={icon} size={14} />
        <span className="tablet:sr-only">{label}</span>
        {staleNote}
        <Icon name="down" size={12} className="text-text-3" />
      </button>
      <span className="flex items-baseline gap-1.25">
        <span className="num text-bpm font-semibold tracking-[-0.02em] text-text">{formatBpm(bpm)}</span>
        <span className="text-[10px] font-semibold tracking-[0.08em] text-text-3">BPM</span>
      </span>
      {pips}
      <span className="num text-[11.5px] whitespace-nowrap text-text-3 tablet:hidden">bar {bar}</span>
      <button
        type="button"
        onClick={onTap}
        className="h-7 rounded-chip border border-line-strong bg-control-hover px-3 text-meta font-bold tracking-[0.06em] text-text uppercase"
      >
        Tap
      </button>
    </div>
  )
}

/** Four beat pips; the downbeat is wider. `beat` null means stopped. */
function Pips({ beat, variant }: { beat: number | null; variant: 'bar' | 'strip' }) {
  const strip = variant === 'strip'
  return (
    <span
      role={beat === null ? undefined : 'img'}
      aria-label={beat === null ? undefined : `Beat ${beat} of 4`}
      aria-hidden={beat === null ? true : undefined}
      className={cx('flex items-center gap-1.25', strip && 'flex-1')}
    >
      {[1, 2, 3, 4].map((n) => (
        <span
          key={n}
          className={cx(
            strip ? 'h-3 rounded-[3px]' : 'h-2.5 rounded-[2px]',
            n === 1 ? (strip ? 'w-4' : 'w-3.5') : strip ? 'w-3' : 'w-2.5',
            n === beat ? 'bg-text shadow-[0_0_10px] shadow-text/55' : 'bg-control-hover',
          )}
        />
      ))}
    </span>
  )
}
