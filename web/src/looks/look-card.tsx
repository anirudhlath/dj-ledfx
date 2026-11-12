// §6.4 LookCard, as Looks.html draws it (F5 rulings 13 to 16 and 18): the look's thumb, its name in serif, a two-line
// description and the inputs it lists. The thumb carries the pill (ruling 13: the first zone the look runs on and how many more,
// in words for a screen reader; ruling 14: "From <look>" for a saved variation, which loses to the running pill, the news) and,
// on hover or focus, a scrim with Put on… and Edit (§6.4: "white border, bottom gradient scrim"). The name is a link to the
// editor stretched over the whole card, so a tap anywhere opens it, and it is Edit's keyboard path (ruling 15), which is why Edit
// itself is out of the tab order. The star (ruling 16) is `setStarred()`'s: the card shows the choice at once and says a failure
// aloud (`failureText()` through the Announcer).
//
// Layers. `LookThumb` is aria-hidden, so what is interactive sits beside it, in a layer over the thumb's padding box (Looks.html's
// overlays are `position: absolute; inset: 0` inside the thumb's 1 px border). The name link's ::after covers the card, so that layer
// and the star sit above it (`z-1`), and the layer takes no pointer itself: a tap on the thumb falls through to the link, and the
// scrim's links take a pointer only while the scrim shows (a touch screen never shows it, so its invisible buttons never catch a tap).
import { useId } from 'react'
import { Link } from 'react-router'
import { failureText, setStarred } from '@/api/actions'
import type { Look } from '@/api/contract'
import { composerLink, type MissingInput } from '@/compose/model'
import { useAnnounce } from '@/design/announce'
import { ButtonLink } from '@/design/button'
import { cx } from '@/design/cx'
import { Icon } from '@/design/icon'
import { LIVE_SPEC } from '@/design/live-numbers'
import { cardInputs, runningPill } from './library-model'
import { LookThumb } from './look-thumb'

export interface LookCardProps {
  look: Look
  /** The names of the zones that run the look (`runningOn()`), in /api/running's order. */
  running: readonly string[]
  /** The name of the look a saved variation was made from (`parentName()`), or null. */
  parent: string | null
  /** The inputs it would wait for (`missingInputs()`). */
  missing: readonly MissingInput[]
}

// Looks.html's pill: 22 px of content, a 1 px border each side and no box-sizing, so the render draws it 24 px high (h-6 here, where
// every box is border-box), 8 px in from the thumb's padding box. §6.4's text-label at 600; the dot is its 6 px live dot (§5.4).
const PILL = 'absolute top-2 left-2 inline-flex h-6 items-center rounded-pill border border-line bg-bg/82 px-2 text-label font-semibold'

export function LookCard({ look, running, parent, missing }: LookCardProps) {
  const nameId = useId()
  const announce = useAnnounce()
  const where = runningPill(running)
  const inputs = cardInputs(look, missing)

  const star = () => {
    const action = `${look.starred ? 'unstar' : 'star'} ${look.name}`
    setStarred(look.id, !look.starred).catch((error: unknown) => announce(failureText(action, error)))
  }

  return (
    <article aria-labelledby={nameId} data-look={look.id} className="group relative flex min-w-0 flex-col gap-2">
      <div className="relative">
        <LookThumb lookId={look.id} size="card" className="group-hover:border-text group-focus-within:border-text" />
        {/* Looks.html's overlays are inside the thumb's border; the radius is the thumb's less that border. */}
        <div className="pointer-events-none absolute inset-px z-1 overflow-hidden rounded-[calc(var(--radius-tile)-1px)]">
          {where ? (
            <span aria-hidden="true" className={cx(PILL, 'gap-1.5 text-text')}>
              <span className="size-1.5 rounded-full bg-text animate-[livedot_2s_ease-in-out_infinite]" />
              {where.shown}
            </span>
          ) : (
            parent !== null && <span className={cx(PILL, 'text-text-2')}>From {parent}</span>
          )}
          <div className="absolute inset-0 flex items-end justify-center gap-2 bg-linear-to-t from-bg/85 to-bg/0 to-70% p-2.5 opacity-0 transition-opacity duration-(--duration-fast) ease-out group-focus-within:opacity-100 group-hover:opacity-100">
            <ButtonLink
              variant="primary"
              size="sm"
              icon="play"
              className="pointer-events-none group-focus-within:pointer-events-auto group-hover:pointer-events-auto"
              {...composerLink(null, look.id)}
            >
              Put on…
            </ButtonLink>
            <ButtonLink
              size="sm"
              icon="sliders"
              to={`/looks/${look.id}`}
              tabIndex={-1}
              className="pointer-events-none group-focus-within:pointer-events-auto group-hover:pointer-events-auto"
            >
              Edit
            </ButtonLink>
          </div>
        </div>
      </div>
      {where && <span className="sr-only">{where.spoken}</span>}
      <div className="flex items-center justify-between gap-1 pl-0.5">
        <h3 id={nameId} className="font-serif text-display-xs text-text" style={{ fontSize: LIVE_SPEC.lookCard.namePx }}>
          <Link to={`/looks/${look.id}`} className="after:absolute after:inset-0">
            {look.name}
          </Link>
        </h3>
        <button
          type="button"
          aria-label={`${look.starred ? 'Unstar' : 'Star'} ${look.name}`}
          aria-pressed={look.starred}
          className={cx(
            'relative z-1 inline-flex size-7 shrink-0 items-center justify-center rounded-chip transition-colors duration-(--duration-fast) ease-out hover:bg-control hover:text-text max-md:touch-target',
            look.starred ? 'text-text' : 'text-text-3',
          )}
          onClick={star}
        >
          <Icon name="star" size={15} className={look.starred ? 'fill-current' : undefined} />
        </button>
      </div>
      {/* Looks.html's description is two lines of 12 px at 1.45, 35 px high whether it fills them or not, so the cards in a row line up. */}
      <p className="-mt-1 line-clamp-2 h-[35px] pl-0.5 text-meta text-text-3">{look.description}</p>
      {/* Looks.html's input names are 11.5 px, the size LookTile's signal line takes from it. */}
      <div className="flex gap-2.5 pl-0.5">
        {inputs.length === 0 ? (
          <span className="text-[11.5px] text-text-3">No input</span>
        ) : (
          inputs.map((input) => (
            <span
              key={input.kind}
              className={cx('inline-flex items-center gap-1 text-[11.5px] font-semibold', input.missing ? 'text-signal' : 'text-text-3')}
            >
              <Icon name={input.icon} size={13} />
              {input.name}
            </span>
          ))
        )}
      </div>
    </article>
  )
}
