import type { ReactElement, ReactNode } from 'react'
import { cx } from '@/design/cx'
import { Icon } from '@/design/icon'
import type { IconName } from '@/design/icons'
import { formatBpm } from '@/lib/format'
import type { TempoSource, TempoState } from './state'

export interface TempoModuleProps extends TempoState {
  /** "bar": the desktop top bar. "strip": the phone strip under the header on Live. */
  variant: 'bar' | 'strip'
  onSourceClick?: () => void
  /** Desktop: wraps the source button, e.g. in F3's tempo source popover as its trigger. */
  renderSource?: (source: ReactElement) => ReactNode
  onTap?: () => void
}

const SOURCE: Record<TempoSource, { label: string; icon: IconName }> = {
  prodjlink: { label: 'Pro DJ Link', icon: 'deck' },
  music: { label: 'Music', icon: 'music' },
  internal: { label: 'Internal', icon: 'tempo' },
}

/** §6.2 TempoModule. F0 draws a still beat; F3 drives the pips from the beat clock (§5.4). */
export function TempoModule({ variant, source, bpm, beat, bar, stale, onSourceClick, renderSource, onTap }: TempoModuleProps) {
  const { label, icon } = SOURCE[source]
  const staleNote = stale && <span className="sr-only">, stale</span>
  const pips = <Pips beat={stale ? null : beat} variant={variant} />

  if (variant === 'strip') {
    return (
      // The strip's own width sets its gaps, not the window's, so the specimen draws what each
      // phone shows. Narrower than a 360 px phone's strip they tighten, which keeps TAP inside down
      // to 320 px (the WCAG reflow width).
      <div className="@container">
        <div
          role="group"
          aria-label="Tempo"
          className="flex h-(--phone-tempo-h) items-center gap-3 rounded-card border border-line bg-raised pr-1 pl-3 @max-[20.5rem]:gap-2"
        >
          {/* The label gives way first, so a long source ("Pro DJ Link") never pushes TAP out. */}
          <span className={cx('inline-flex min-w-0 items-center gap-1.5 text-data font-semibold', stale ? 'text-signal' : 'text-text-2')}>
            <Icon name={icon} size={16} />
            <span className="min-w-0 truncate">{label}</span>
            {staleNote}
          </span>
          <span className="num text-bpm font-semibold tracking-[-0.02em]">
            {formatBpm(bpm)}
            <span className="sr-only"> BPM</span>
          </span>
          {pips}
          {/* The face is Phone-Live.png's; touch-target grows its hit area to --touch-min (§6). */}
          <button
            type="button"
            onClick={onTap}
            className="h-10 rounded-[9px] border border-line-strong bg-control-hover px-4 text-size-control font-bold tracking-[0.06em] uppercase max-md:touch-target"
          >
            Tap
          </button>
        </div>
      </div>
    )
  }

  const sourceButton = (
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
  )

  return (
    <div
      role="group"
      aria-label="Tempo"
      // Sized by its content: a longer source or bar number widens the module, it never squeezes
      // below its content, and the top bar's title truncates before TAP leaves it.
      className="flex h-10 items-center gap-3 rounded-tile border border-line bg-raised px-1.5"
    >
      {renderSource ? renderSource(sourceButton) : sourceButton}
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

const PIPS: Record<TempoModuleProps['variant'], { row?: string; pip: string; downbeat: string; beat: string }> = {
  bar: { pip: 'h-2.5 rounded-[2px]', downbeat: 'w-3.5', beat: 'w-2.5' },
  strip: { row: 'flex-1', pip: 'h-3 rounded-[3px]', downbeat: 'w-4', beat: 'w-3' },
}

/** Four beat pips; the downbeat is wider. `beat` null means stopped. */
function Pips({ beat, variant }: { beat: number | null; variant: TempoModuleProps['variant'] }) {
  const size = PIPS[variant]
  const a11y = beat === null ? { 'aria-hidden': true } : { role: 'img', 'aria-label': `Beat ${beat} of 4` }
  return (
    <span {...a11y} className={cx('flex items-center gap-1.25', size.row)}>
      {[1, 2, 3, 4].map((n) => (
        <span
          key={n}
          className={cx(size.pip, n === 1 ? size.downbeat : size.beat, n === beat ? 'bg-text shadow-[0_0_10px] shadow-text/55' : 'bg-control-hover')}
        />
      ))}
    </span>
  )
}
