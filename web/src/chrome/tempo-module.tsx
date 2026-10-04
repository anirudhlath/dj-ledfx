import { useRef, type CSSProperties, type ReactElement, type ReactNode } from 'react'
import { cx } from '@/design/cx'
import { Icon } from '@/design/icon'
import { formatBpm } from '@/lib/format'
import { PIP_STYLE, usePips } from './pip-writer'
import { NO_DJ, TEMPO_SOURCES } from './sources'
import type { TempoState } from './state'

/** A beat drawn as given, never from the beat clock: the /system specimen's. */
export interface FixedBeat {
  /** 1–4. */
  beat: number
  /** null: no "bar N". */
  bar: number | null
}

export interface TempoModuleProps extends TempoState {
  /** "bar": the desktop top bar. "strip": the phone strip under the header on Live. */
  variant: 'bar' | 'strip'
  /** The specimen's fixed beat. The app passes none: the pip writer follows the beat clock. */
  fixed?: FixedBeat
  onSourceClick?: () => void
  /** Desktop: wraps the source button, e.g. in the tempo source popover as its trigger. */
  renderSource?: (source: ReactElement) => ReactNode
  onTap?: () => void
}

/**
 * §6.2 TempoModule. The pips and "bar N" follow the beat clock, written by the pip writer from an animation
 * frame (F3 decision 3), so a beat redraws no React. With no DJ (`bpm` null) it's §9.3's Idle: a quiet
 * "No DJ" where the source is, and no BPM or pips.
 */
export function TempoModule({ variant, source, bpm, stale, lock, held, bars, fixed, onSourceClick, renderSource, onTap }: TempoModuleProps) {
  const idle = bpm === null
  const named = idle ? NO_DJ : TEMPO_SOURCES[source]
  // F3 decision 6: the hold is said in words. Only Internal holds; the beat's source catches up with the
  // inputs push within a beat message.
  const label = held && source === 'internal' && !idle ? `${named.label} · held` : named.label
  const { icon } = named
  // F3 decision 5: under these locks the engine refuses a tap.
  const tapLocked = lock === 'prodjlink' || lock === 'music'
  const staleNote = stale && <span className="sr-only">, stale</span>
  const pips = <Pips variant={variant} stale={stale} bars={bars} fixed={fixed} />
  const tone = idle ? 'text-text-3' : stale ? 'text-signal' : 'text-text-2'

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
          <span className={cx('inline-flex min-w-0 items-center gap-1.5 text-data font-semibold', tone)}>
            <Icon name={icon} size={16} />
            <span className="min-w-0 truncate">{label}</span>
            {staleNote}
          </span>
          {!idle && (
            <span className="num text-bpm font-semibold tracking-[-0.02em]">
              {formatBpm(bpm)}
              <span className="sr-only"> BPM</span>
            </span>
          )}
          {/* Idle, the pips' room keeps TAP at the strip's end. */}
          {idle ? <span className="flex-1" /> : pips}
          {/* The face is Phone-Live.png's; touch-target grows its hit area to --touch-min (§6). */}
          <button
            type="button"
            onClick={onTap}
            disabled={tapLocked}
            className="h-10 rounded-[9px] border border-line-strong bg-control-hover px-4 text-size-control font-bold tracking-[0.06em] uppercase disabled:pointer-events-none disabled:opacity-45 max-md:touch-target"
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
      className={cx(
        'inline-flex h-7 items-center gap-1.5 rounded-chip px-2 text-meta font-semibold',
        // Idle is a quiet chip (§9.3, State-Sheet.png): outlined, not filled.
        idle ? 'border border-line bg-transparent' : 'bg-control',
        tone,
      )}
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
      {!idle && (
        <span className="flex items-baseline gap-1.25">
          <span className="num text-bpm font-semibold tracking-[-0.02em] text-text">{formatBpm(bpm)}</span>
          <span className="text-[10px] font-semibold tracking-[0.08em] text-text-3">BPM</span>
        </span>
      )}
      {!idle && pips}
      <button
        type="button"
        onClick={onTap}
        disabled={tapLocked}
        className="h-7 rounded-chip border border-line-strong bg-control-hover px-3 text-meta font-bold tracking-[0.06em] text-text uppercase disabled:pointer-events-none disabled:opacity-45"
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

/**
 * Four beat pips, the downbeat wider, and on desktop "bar N" after them. The pip writer lights them and
 * names the row and the bar from the beat clock; a fixed beat is drawn as given. Stale, they stop and the
 * row leaves the accessibility tree.
 */
function Pips({ variant, stale, bars, fixed }: {
  variant: TempoModuleProps['variant']
  stale: boolean
  bars: boolean
  fixed?: FixedBeat
}) {
  const size = PIPS[variant]
  const row = useRef<HTMLSpanElement>(null)
  // The bar is drawn here, not beside the pips in TempoModule, so its ref is set before the writer's
  // first write (a layout effect sees its own component's refs, not a later sibling's).
  const bar = useRef<HTMLSpanElement>(null)
  usePips(fixed === undefined ? row : null, bar, stale)
  const a11y = stale
    ? { 'aria-hidden': true }
    : { role: 'img', ...(fixed === undefined ? {} : { 'aria-label': `Beat ${fixed.beat} of 4` }) }
  return (
    <>
      <span ref={row} {...a11y} className={cx('flex items-center gap-1.25', size.row)}>
        {[1, 2, 3, 4].map((n) => (
          <span
            key={n}
            className={cx(size.pip, n === 1 ? size.downbeat : size.beat)}
            style={fixed !== undefined && !stale && n === fixed.beat ? ({ ...PIP_STYLE, '--pip': 1 } as CSSProperties) : PIP_STYLE}
          />
        ))}
      </span>
      {variant === 'bar' && (fixed === undefined ? bars : fixed.bar !== null) && (
        // The pip writer writes "bar N" here; a fixed beat's bar is drawn as given.
        <span ref={bar} className="num text-[11.5px] whitespace-nowrap text-text-3 tablet:hidden">
          {fixed?.bar != null && `bar ${fixed.bar}`}
        </span>
      )}
    </>
  )
}
