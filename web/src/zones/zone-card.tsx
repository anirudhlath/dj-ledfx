// §6.3 ZoneCard: a running zone in every state (running, transition, slow, crashed, waiting), full or
// compact (F3 decision 2). What it says is zone-view.ts's; what it does goes through src/api's actions, and
// a failure is said in words (Review Focus 1). Look and layout: Main.html's, State-Transition.html's and
// State-Problems.html's cards. The swatches follow the frame store without React (Task 8).
import { useRef, useState } from 'react'
import { failureText, restartZone, setBrightness, turnOff } from '@/api/actions'
import type { RunningZone } from '@/api/contract'
import { useConnectionStatus } from '@/chrome/hooks'
import { useAnnounce } from '@/design/announce'
import { Button, ButtonLink } from '@/design/button'
import { Chip } from '@/design/chip'
import { cx } from '@/design/cx'
import { Icon } from '@/design/icon'
import { ProgressBar } from '@/design/progress-bar'
import { Slider } from '@/design/slider'
import { LightSwatch } from '@/lights/light-swatch'
import { useMovingProgress } from './use-moving-progress'
import { useThrottledValue } from './use-throttled-value'
import { ZoneMenu } from './zone-menu'
import type { TransitionView, ZoneNote, ZoneView } from './zone-view'

export interface ZoneCardProps {
  running: RunningZone
  view: ZoneView
  /** F3 decision 2: the look's name smaller and the padding tighter; the view has dropped the lights' note. */
  compact?: boolean
  /** The card /live/zones/:zoneId names (F3 decision 23), outlined as the renders draw focus. */
  outlined?: boolean
  /** The lights' swatches; State-Firmware's card has none, its breakdown having each light's. */
  swatches?: boolean
}

/** §6.3's note: what's wrong or special. */
export function ZoneNoteText({ note, className }: { note: ZoneNote; className?: string }) {
  return (
    <p className={cx('text-meta', note.tone === 'signal' ? 'text-signal' : 'text-text-3', className)}>
      {note.parts.map((part, index) => (
        <span key={index} className={cx(part.strong && 'font-semibold text-signal', part.mono && 'num')}>
          {part.text}
        </span>
      ))}
    </p>
  )
}

/** The look's name; in a transition, the old one struck through, then the new (State-Transition). */
function LookName({ view, compact }: { view: ZoneView; compact: boolean }) {
  if (view.transition === null) {
    return <h3 className={cx('font-serif tracking-[-0.005em]', compact ? 'text-display-sm' : 'text-display-md')}>{view.lookName}</h3>
  }
  // The spaces sit between the parts, where the name is read whole ("from Fireflies to Embers"); a flex
  // container draws no whitespace-only text, so they change nothing on screen.
  return (
    <h3 className="flex flex-wrap items-baseline gap-2.5 font-serif">
      <span className="sr-only">from</span>{' '}
      <s className="text-[24px] leading-[1.05] text-text-3 decoration-1">{view.transition.from}</s>{' '}
      <Icon name="right" className="self-center text-text-3" />
      <span className="sr-only">to</span>{' '}
      <span className="text-[28px] leading-[1.05]">{view.lookName}</span>
    </h3>
  )
}

/** Input chips (or a quiet "No inputs"), modifier chips, and the since line (§6.3 item 3). */
function Meta({ view }: { view: ZoneView }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {view.inputs?.length === 0 && <Chip variant="quiet">No inputs</Chip>}
      {view.inputs?.map((input) => (
        <Chip key={input.kind} variant={input.waiting ? 'signal' : 'input'} icon={input.icon}>
          {input.label}
        </Chip>
      ))}
      {view.modifiers.map((modifier) => (
        <Chip key={modifier} variant="mod">
          {modifier}
        </Chip>
      ))}
      <span className="ml-0.5 text-meta whitespace-nowrap text-text-3">{view.since}</span>
    </div>
  )
}

/** "Dissolve · 3 s" and "62%" over the bar (State-Transition), moving on by themselves (F3 decision 16). */
function TransitionBar({ transition }: { transition: TransitionView }) {
  const percent = useRef<HTMLSpanElement>(null)
  const bar = useRef<HTMLSpanElement>(null)
  useMovingProgress(transition.progress, transition.durationS, percent, bar)
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex justify-between text-meta text-text-2">
        <span>{transition.label}</span>
        <span ref={percent} />
      </div>
      <ProgressBar ref={bar} value={transition.progress} label={transition.label} />
    </div>
  )
}

export function ZoneCard({ running, view, compact = false, outlined = false, swatches = true }: ZoneCardProps) {
  const announce = useAnnounce()
  const linked = useConnectionStatus() !== 'reconnecting'
  const [busy, setBusy] = useState(false)
  const brightness = useThrottledValue({
    server: running.brightness,
    send: (value) => setBrightness(running.zoneId, value),
    onFail: (error) => announce(failureText(`change the brightness of ${view.name}`, error)),
    enabled: linked,
  })
  const act = (action: () => Promise<void>, what: string) => {
    setBusy(true)
    action()
      .catch((error: unknown) => announce(failureText(what, error)))
      .finally(() => setBusy(false))
  }
  const off = () => act(() => turnOff(running.zoneId), `turn off ${view.name}`)
  const restart = () => act(() => restartZone(running.zoneId), `restart ${view.lookName}`)
  const crashed = running.state === 'crashed'
  const offButton = (
    <Button variant="outline" size="sm" icon="power" aria-label={`Turn off ${view.name}`} disabled={busy} onClick={off}>
      Off
    </Button>
  )
  return (
    <article
      aria-label={`${view.name} — ${view.lookName}`}
      data-zone={running.zoneId}
      data-shape={compact ? 'compact' : 'card'}
      className={cx(
        'flex flex-col rounded-card border bg-raised',
        compact ? 'gap-2.5 px-3.5 pt-3 pb-3.5' : 'gap-3 px-4 pt-3.5 pb-4',
        // §6.3 crashed: "signal border".
        crashed ? 'border-signal-line' : 'border-line',
        outlined && 'outline-2 outline-offset-2 outline-text',
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-baseline gap-2">
          <span className="text-data font-semibold whitespace-nowrap text-text-2">{view.name}</span>
          <span className="truncate text-meta text-text-3">{view.context}</span>
        </div>
        <ZoneMenu zoneId={running.zoneId} zoneName={view.name} lookId={running.lookId} onRestart={restart} />
      </div>
      <LookName view={view} compact={compact} />
      <Meta view={view} />
      {view.transition !== null && <TransitionBar transition={view.transition} />}
      {swatches && view.lights.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.75">
          {view.lights.map(({ light, state }) => (
            <LightSwatch key={light.id} light={light} state={state} />
          ))}
        </div>
      )}
      {view.notes.map((note, index) => (
        <ZoneNoteText key={index} note={note} />
      ))}
      {crashed ? (
        // §6.3 crashed: "controls become Restart · Details · Off".
        <div className="flex gap-2">
          <Button size="sm" icon="refresh" disabled={busy} onClick={restart}>
            Restart
          </Button>
          <ButtonLink variant="ghost" size="sm" to={`/looks/${encodeURIComponent(running.lookId)}`}>
            Details
          </ButtonLink>
          <div className="grow" />
          {offButton}
        </div>
      ) : (
        <div className="flex items-center gap-3">
          <Icon name="sun" size={15} className="shrink-0 text-text-3" />
          <Slider
            label={`Brightness for ${view.name}`}
            value={Math.round(brightness.value * 100)}
            onValueChange={(percent) => brightness.change(percent / 100)}
            format={(percent) => `${percent}%`}
            className="flex-1"
          />
          {offButton}
        </div>
      )}
    </article>
  )
}
