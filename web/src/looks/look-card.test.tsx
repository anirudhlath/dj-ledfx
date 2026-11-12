import { QueryClientProvider, useQuery } from '@tanstack/react-query'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useLocation } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import { composerEntered, composerLink } from '@/compose/model'
import { lookName } from '@/api/mocks/fixtures'
import { queries, queryClient } from '@/api/queries'
import { api, ApiError } from '@/api/rest'
import { Announcer } from '@/design/announcer'
import { LIVE_SPEC } from '@/design/live-numbers'
import { formatList } from '@/lib/format'
import { seedRest } from '@/test/rest'
import { renderAt } from '@/test/router'
import { LookCard, type LookCardProps } from './look-card'
import { LIBRARY } from './looks-render'

/**
 * A card as the page draws it: the look comes from REST's cache, so a star written there redraws the card (Task 9's page does the same).
 * `where` says where a link took the router, and what history state it carried.
 */
function Card({ id, ...rest }: Partial<Omit<LookCardProps, 'look'>> & { id: string }) {
  const look = useQuery(queries.looks()).data!.find((each) => each.id === id)!
  const { pathname, search, state } = useLocation()
  return (
    <>
      <LookCard look={look} running={[]} parent={null} missing={[]} {...rest} />
      <p data-testid="where">{`${pathname}${search} ${composerEntered(state) ? 'composer' : 'plain'}`}</p>
    </>
  )
}

function renderCard(id: string, rest: Partial<Omit<LookCardProps, 'look'>> = {}) {
  const state = seedRest('library')
  const look = state.looks.find((each) => each.id === id)!
  const { unmount } = renderAt(
    '/looks',
    <QueryClientProvider client={queryClient}>
      <Announcer news="">
        <Card id={id} {...rest} />
      </Announcer>
    </QueryClientProvider>,
  )
  return { state, look, card: screen.getByRole('article', { name: look.name }), unmount }
}

/** `api.setStarred`, answering as the server does: the look with its star as it was asked. */
const serveStars = () =>
  vi.spyOn(api, 'setStarred').mockImplementation(async (id, starred) => ({
    ...queryClient.getQueryData(queries.looks().queryKey)!.find((each) => each.id === id)!,
    starred,
  }))

describe('LookCard (§6.4)', () => {
  // Looks.html's cards: the serif name, the two-line description and the inputs, each in its own row.
  it("draws the look's name in serif at §6.4's size, its description, and its inputs", () => {
    const { look, card } = renderCard('drop')
    expect(card).toHaveAttribute('data-look', look.id)
    const name = within(card).getByRole('heading', { level: 3, name: look.name })
    expect(name).toHaveClass('font-serif')
    expect(name).toHaveStyle({ fontSize: `${LIVE_SPEC.lookCard.namePx}px` })
    expect(within(card).getByText(look.description!)).toBeInTheDocument()
    const inputs = LIBRARY.inputs[look.id]
    expect(inputs.length).toBeGreaterThan(0)
    for (const input of inputs) expect(within(card).getByText(input)).toBeInTheDocument()
    expect(within(card).queryByText('No input')).not.toBeInTheDocument()
  })

  it('says "No input" for a look with none, and draws a missing input in signal', () => {
    const none = renderCard('fireflies')
    expect(within(none.card).getByText('No input')).toHaveClass('text-text-3')
    none.unmount()

    const { card } = renderCard('drop', { missing: ['music'] })
    const [first, ...others] = LIBRARY.inputs.drop
    expect(first).toBe('Music')
    expect(within(card).getByText(first)).toHaveClass('text-signal')
    for (const input of others) expect(within(card).getByText(input)).toHaveClass('text-text-3')
    expect(within(card).queryByText('No input')).not.toBeInTheDocument()
  })

  // F5 ruling 15.
  it('opens the editor from its name, and puts the look on from Put on…', async () => {
    const user = userEvent.setup()
    const { look, card } = renderCard('embers')
    expect(within(card).getByRole('link', { name: look.name })).toHaveAttribute('href', `/next/looks/${look.id}`)
    expect(within(card).getByRole('link', { name: 'Put on…' })).toHaveAttribute('href', `/next${composerLink(null, look.id).to}`)
    // The name link is Edit's keyboard path, so Edit itself is left out of the tab order.
    const edit = within(card).getByText('Edit').closest('a')
    expect(edit).toHaveAttribute('href', `/next/looks/${look.id}`)
    expect(edit).toHaveAttribute('tabindex', '-1')

    // Put on… enters the composer as every link into it does, so Cancel steps back out to the library.
    await user.click(within(card).getByRole('link', { name: 'Put on…' }))
    expect(screen.getByTestId('where')).toHaveTextContent(`${composerLink(null, look.id).to} composer`)
  })

  it('stars and unstars the look, saying so with aria-pressed and its label', async () => {
    const user = userEvent.setup()
    serveStars()
    const { look, card } = renderCard('sunset')
    const star = within(card).getByRole('button', { name: `Star ${look.name}` })
    expect(star).toHaveAttribute('aria-pressed', 'false')
    expect(star.querySelector('svg')).not.toHaveClass('fill-current')
    await user.click(star)
    expect(api.setStarred).toHaveBeenLastCalledWith(look.id, true)
    const starred = await within(card).findByRole('button', { name: `Unstar ${look.name}` })
    expect(starred).toHaveAttribute('aria-pressed', 'true')
    expect(starred.querySelector('svg')).toHaveClass('fill-current')

    await user.click(starred)
    expect(api.setStarred).toHaveBeenLastCalledWith(look.id, false)
    expect(await within(card).findByRole('button', { name: `Star ${look.name}` })).toHaveAttribute('aria-pressed', 'false')
  })

  // F5 plan, Review Focus 3: a failed star is said aloud, and the card shows the look as it was.
  it('says a failed star aloud, and shows the look as it was', async () => {
    const user = userEvent.setup()
    vi.spyOn(api, 'setStarred').mockRejectedValue(new ApiError(500, 'Internal Server Error', '/api/looks/sunset/starred'))
    const { look, card } = renderCard('sunset')
    await user.click(within(card).getByRole('button', { name: `Star ${look.name}` }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent(`Couldn't star ${look.name}. Internal Server Error`))
    expect(within(card).getByRole('button', { name: `Star ${look.name}` })).toHaveAttribute('aria-pressed', 'false')
  })

  it('says a failed unstar as an unstar, and keeps the star', async () => {
    const user = userEvent.setup()
    vi.spyOn(api, 'setStarred').mockRejectedValue(new ApiError(0, 'Failed to fetch', '/api/looks/fireflies/starred'))
    const { look, card } = renderCard('fireflies')
    await user.click(within(card).getByRole('button', { name: `Unstar ${look.name}` }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent(`Couldn't unstar ${look.name}. The server didn't answer.`))
    expect(within(card).getByRole('button', { name: `Unstar ${look.name}` })).toHaveAttribute('aria-pressed', 'true')
  })

  // F5 plan, Review Focus 2: the pill names the first zone, and a screen reader hears them all.
  it('names the zone it runs on, and every zone in words when there are more', () => {
    const [alpha, beta] = seedRest('library').zones.map((zone) => zone.name)
    const one = renderCard('fireflies', { running: [alpha] })
    const pill = within(one.card).getByText(alpha)
    // Looks.html's pill: the live dot, then the zone.
    expect(pill.querySelectorAll('span')).toHaveLength(1)
    expect(pill).toHaveAttribute('aria-hidden', 'true')
    expect(within(one.card).getByText(`Running on ${alpha}`)).toHaveClass('sr-only')
    one.unmount()

    const several = renderCard('fireflies', { running: [alpha, beta] })
    expect(within(several.card).getByText(`${alpha} +1`)).toBeInTheDocument()
    expect(within(several.card).getByText(`Running on ${formatList([alpha, beta])}`)).toHaveClass('sr-only')
  })

  it('draws no pill for a look that runs nowhere and is no variation', () => {
    const { card } = renderCard('fireflies')
    expect(within(card).queryByText(/Running on|^From /)).not.toBeInTheDocument()
  })

  // F5 ruling 14: the same pill without the dot, in text-2.
  it('says which look a saved look came from', () => {
    const parent = lookName(LIBRARY.mine[0].from)
    const { card } = renderCard('mine-1', { parent })
    const pill = within(card).getByText(`From ${parent}`)
    expect(pill.querySelector('span')).toBeNull()
    expect(pill).toHaveClass('text-text-2')
    expect(within(card).queryByText(/^Running on/)).not.toBeInTheDocument()
  })

  // F5 rulings 13 and 14 share one pill: where a saved look runs somewhere, that is the news.
  it('says where a saved look runs, ahead of where it came from', () => {
    const [zone] = seedRest('library').zones.map((each) => each.name)
    const { card } = renderCard('mine-1', { running: [zone], parent: lookName(LIBRARY.mine[0].from) })
    expect(within(card).getByText(zone)).toBeInTheDocument()
    expect(within(card).queryByText(/^From /)).not.toBeInTheDocument()
  })

  // §6.4: "Hover (and focus): white border, bottom gradient scrim".
  it("turns the thumb's border to text on hover and on focus, and keeps the scrim's links off the pointer until then", () => {
    const { card } = renderCard('embers')
    expect(card).toHaveClass('group')
    expect(card.querySelector('[data-thumb]')).toHaveClass('border-line', 'group-hover:border-text', 'group-focus-within:border-text')
    const put = within(card).getByRole('link', { name: 'Put on…' })
    const scrim = put.parentElement!
    expect(scrim).toHaveClass('opacity-0', 'group-hover:opacity-100', 'group-focus-within:opacity-100')
    // A scrim that's drawn at opacity 0 must not take a tap: on a touch screen it never shows, so the tap opens the editor.
    expect(put).toHaveClass('pointer-events-none', 'group-hover:pointer-events-auto', 'group-focus-within:pointer-events-auto')
    expect(within(card).getByText('Edit').closest('a')).toHaveClass('pointer-events-none', 'group-hover:pointer-events-auto')
  })
})
