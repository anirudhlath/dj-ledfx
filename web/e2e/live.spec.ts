import { expect, test, type Locator, type Page } from '@playwright/test'
import { open, stageCanvas } from './helpers'

// The hero moment (spec §12.5): Wednesday 23 September, 19:14 in Dallas (timezoneId in the config).
const HERO_TIME = new Date('2026-09-23T19:14:00-05:00')

/** The path with ?still: the mock holds the beat and the frames, so a screenshot is the same every run. */
const still = (path: string) => `${path}${path.includes('?') ? '&' : '?'}still`

/** Opens the attention list: the desktop popover, or the phone's sheet. */
async function openAttention(page: Page) {
  await page.getByRole('banner').getByRole('button', { name: /needs? attention$/ }).click()
  await expect(page.getByRole('dialog', { name: 'Needs attention', exact: true })).toBeVisible()
}

/** What the link's drop changes from run to run: the retry's count, and when the last frame came. */
const reconnectingMask = (page: Page) => [page.getByText(/try \d+/), page.getByText(/last frame/i)]

interface State {
  /** The screenshot's name; Playwright adds the project's. */
  name: string
  path: string
  /** The render its baseline is compared with by eye; null for a §9 state no render draws. */
  render: string | null
  /** What shows once the state is drawn. */
  ready: (page: Page) => Locator
  /** Opens what the render shows open. */
  then?: (page: Page) => Promise<void>
  mask?: (page: Page) => Locator[]
  /** Nothing needs attention, so the phone's header has no attention button for open() to wait for. */
  quiet?: true
  /** The desktop banner draws no frame rate: nothing runs, or the link is down. */
  rateless?: true
}

// §13.1 F3 ("M3" there): every Live state from §9, from a mock scenario. The hero is shell.spec.ts's `Live`.
const DESKTOP: State[] = [
  { name: 'doorbell', path: '/next/live?scenario=doorbell', render: 'Live-Doorbell', ready: (page) => page.getByRole('article', { name: 'Doorbell ripple over everything' }) },
  { name: 'transition', path: '/next/live?scenario=transition', render: 'State-Transition', ready: (page) => page.getByText('Dissolve · 3 s', { exact: true }) },
  { name: 'problems', path: '/next/live?scenario=problems', render: 'State-Problems', ready: (page) => page.getByRole('article', { name: 'Kitchen — Lava' }), then: openAttention },
  { name: 'firmware', path: '/next/live?scenario=firmware', render: 'State-Firmware', ready: (page) => page.getByRole('region', { name: 'Lights in Whole home' }) },
  // State-Inputs-Down is F6's Inputs page: compare only its top bar.
  { name: 'inputs-down', path: '/next/live?scenario=inputs-down', render: 'State-Inputs-Down', ready: (page) => page.getByRole('banner').getByRole('button', { name: '3 need attention' }) },
  { name: 'nothing-running', path: '/next/live?scenario=nothing-running', render: 'State-Nothing-Running', ready: (page) => page.getByRole('heading', { name: 'Nothing running' }), rateless: true },
  { name: 'no-lights', path: '/next/live?scenario=no-lights', render: 'State-No-Lights-Placed', ready: (page) => page.getByRole('region', { name: 'Place your 19 lights' }) },
  { name: 'reconnecting', path: '/next/live?scenario=reconnecting', render: 'State-Reconnecting', ready: (page) => page.getByRole('region', { name: 'Lost the live link to homeserver' }), mask: reconnectingMask, rateless: true },
  { name: 'preview-only', path: '/next/live?scenario=preview-only', render: 'State-Preview-Only', ready: (page) => page.getByText('Everything renders here. Nothing is sent to the lights.') },
  { name: 'waiting', path: '/next/live?scenario=waiting', render: null, ready: (page) => page.getByText('Nothing playing on Music Assistant. The look waits dark and starts with the music.') },
  { name: 'first-run', path: '/next/live?scenario=first-run', render: null, ready: (page) => page.getByRole('region', { name: 'No lights yet' }), rateless: true },
]

const PHONE: State[] = [
  { name: 'preview-only', path: '/next/live?scenario=preview-only', render: 'Phone-State-Preview-Only', ready: (page) => page.getByRole('button', { name: 'Turn off preview only' }) },
  { name: 'problems', path: '/next/live?scenario=problems', render: 'Phone-State-Problems', ready: (page) => page.getByRole('article', { name: 'Kitchen — Lava' }), then: openAttention },
  { name: 'reconnecting', path: '/next/live?scenario=reconnecting', render: 'Phone-State-Reconnecting', ready: (page) => page.getByRole('region', { name: 'Lost the live link' }), mask: reconnectingMask },
  { name: 'nothing-running', path: '/next/live?scenario=nothing-running', render: 'Phone-State-Nothing-Running', ready: (page) => page.getByRole('heading', { name: 'Nothing running' }), quiet: true },
  { name: 'zone', path: '/next/live/zones/living', render: 'Phone-Zone', ready: (page) => page.getByRole('region', { name: 'Lights · live' }) },
  { name: 'tempo', path: '/next/inputs?scenario=dj-playing', render: 'Phone-Tempo', ready: (page) => page.getByRole('region', { name: 'Decks' }) },
  { name: 'waiting', path: '/next/live?scenario=waiting', render: null, ready: (page) => page.getByText('Nothing playing on Music Assistant. The look waits dark and starts with the music.') },
  { name: 'first-run', path: '/next/live?scenario=first-run', render: null, ready: (page) => page.getByRole('region', { name: 'No lights yet' }), quiet: true },
]

test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(HERO_TIME)
})

for (const [size, states] of [['desktop', DESKTOP], ['phone', PHONE]] as const) {
  test.describe(`Live's states on ${size === 'desktop' ? 'desktop' : 'the phone'}`, () => {
    test.skip(({ isMobile }) => isMobile !== (size === 'phone'))

    for (const state of states) {
      test(`${state.name}${state.render === null ? '' : `, as ${state.render}`}`, async ({ page }) => {
        await open(page, still(state.path), state.quiet && state.ready(page))
        if (state.path.startsWith('/next/live')) await expect(stageCanvas(page)).toBeVisible()
        await expect(state.ready(page)).toBeVisible()
        // As shell.spec.ts's openStill: Live's tempo drawn, and on desktop the frame rate settled where the banner has one.
        if (state.path.startsWith('/next/live?')) await expect(page.getByRole('banner').getByRole('group', { name: 'Tempo' })).toBeVisible()
        if (size === 'desktop' && !state.rateless) await expect(page.getByRole('banner').getByText('60 fps')).toBeVisible({ timeout: 10_000 })
        await state.then?.(page)
        await expect(page).toHaveScreenshot(`${state.name}.png`, { mask: state.mask?.(page) })
      })
    }
  })
}

// Review focus 1 and §14 Resilience, in the browser: the reconnecting scenario drops the link a
// second after it connects, then refuses every retry. The phone header says the same in its pill
// (shell.test.tsx); this needs one project.
test.describe('the link', () => {
  test.skip(({ isMobile }) => isMobile)

  test('says Reconnecting within 2 s of a drop, and counts the retries', async ({ page }) => {
    await page.goto('/next/live?scenario=reconnecting')
    const banner = page.getByRole('banner')
    await expect(banner.getByRole('button', { name: '1 needs attention' })).toBeVisible()
    const connected = Date.now()

    await expect(page.getByRole('status')).toHaveText('Reconnecting')
    // The mock drops the link 1 s after it connects, and §14 allows 2 s from there.
    expect(Date.now() - connected).toBeLessThan(3000)
    await expect(banner.getByText('· try 1')).toBeVisible()
    // The retry 1 s later is refused, so the count moves on.
    await expect(banner.getByText('· try 2')).toBeVisible({ timeout: 5000 })
    // What the server said before it went stays on screen, and nothing claims All good.
    await expect(banner.getByRole('button', { name: '1 needs attention' })).toBeVisible()
  })

  // §9.4 Reconnecting and Review Focus 3: the cards go inert, the card says when the last frame came, and Try now doesn't wait.
  test('freezes the cards, and Try now retries at once', async ({ page }) => {
    await open(page, '/next/live?scenario=reconnecting')
    const card = page.getByRole('region', { name: 'Lost the live link to homeserver' })
    await expect(card).toBeVisible({ timeout: 5000 })
    await expect(card).toContainText(/This is the last frame, from \d\d:\d\d:\d\d\./)
    await expect(page.locator('[inert] article')).toHaveCount(3)
    const banner = page.getByRole('banner')
    await expect(banner.getByText('· try 2')).toBeVisible({ timeout: 5000 })
    await card.getByRole('button', { name: 'Try now' }).click()
    // The backoff would wait 2 s or more after the second try.
    await expect(banner.getByText('· try 3')).toBeVisible({ timeout: 1000 })
  })
})

test.describe('on desktop', () => {
  test.skip(({ isMobile }) => isMobile)

  // F3 decision 6 and Review Focus 2, on the mock's tempo clock (Task 3).
  test('a tap during a DJ set holds Internal and says so, and Back to Auto gives the tempo back', async ({ page }) => {
    await open(page, '/next/live?scenario=dj-playing')
    const tempo = page.getByRole('banner').getByRole('group', { name: 'Tempo' })
    await expect(tempo.getByRole('button', { name: 'Pro DJ Link' })).toBeVisible()
    await tempo.getByRole('button', { name: 'Tap' }).click()
    await expect(tempo.getByRole('button', { name: 'Internal · held' })).toBeVisible()
    await expect(page.getByRole('status')).toContainText('Tempo held on Internal')
    await tempo.getByRole('button', { name: 'Internal · held' }).click()
    await page.getByRole('dialog', { name: 'Tempo source' }).getByRole('button', { name: 'Back to Auto' }).click()
    await expect(tempo.getByRole('button', { name: 'Pro DJ Link' })).toBeVisible()
    await expect(page.getByRole('status')).toContainText('Tempo back to Pro DJ Link')
  })

  // §5.6: impossible to miss, and one press away from the lights again.
  test('preview only tapes the window, and the stage label sends the lights back', async ({ page }) => {
    await open(page, '/next/live')
    const frame = page.locator('[data-tape="frame"]')
    await expect(frame).toHaveCount(0)
    await page.getByRole('banner').getByRole('switch', { name: 'Preview only' }).click()
    await expect(frame).toHaveCount(1)
    await expect(page.getByText('Everything renders here. Nothing is sent to the lights.')).toBeVisible()
    await page.getByRole('button', { name: 'Send to lights again' }).click()
    await expect(frame).toHaveCount(0)
  })

  // State-Preview-Only draws its label at the stage's top and no stage tools: here the tools and the sun's readout start under it.
  test("preview only's label covers none of the stage's tools", async ({ page }) => {
    await open(page, '/next/live?scenario=preview-only')
    await expect(stageCanvas(page)).toBeVisible()
    const box = async (locator: Locator) => {
      const found = await locator.boundingBox()
      if (!found) throw new Error(`${locator} is not on screen`)
      return found
    }
    const label = await box(page.getByRole('button', { name: 'Send to lights again' }).locator('..'))
    const stage = page.getByRole('region', { name: 'Home, live' })
    for (const tool of [stage.getByRole('switch', { name: 'Labels' }), stage.getByText(/^Sun /).first()]) {
      expect((await box(tool)).y).toBeGreaterThanOrEqual(label.y + label.height)
    }
  })
})

// Owner's difference #6: the phone's preview-only banner keeps Phone-State-Preview-Only's 36 px Turn off, and
// its hit area fills a 44 px band centred on it (CLAUDE.md: `touch-target`), as TAP's does.
test.describe('on the phone', () => {
  test.skip(({ isMobile }) => !isMobile)

  test("preview only's Turn off keeps its drawn face, and answers a touch anywhere in a 44 px band", async ({ page }) => {
    await open(page, '/next/live?scenario=preview-only')
    const box = await page.getByRole('button', { name: 'Turn off preview only' }).boundingBox()
    if (!box) throw new Error('Turn off is not on screen')
    expect(box.height).toBe(36)
    const [x, middle] = [box.x + box.width / 2, box.y + box.height / 2]
    const hits = await page.evaluate(
      (points) => points.map(([px, py]) => document.elementFromPoint(px, py)?.closest('button')?.getAttribute('aria-label') ?? null),
      [
        [x, middle - 21.5],
        [x, middle + 21.5],
      ],
    )
    expect(hits).toEqual(['Turn off preview only', 'Turn off preview only'])
  })
})
