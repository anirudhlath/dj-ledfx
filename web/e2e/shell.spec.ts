import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Locator, type Page } from '@playwright/test'

// The hero moment (spec §12.5): Wednesday 23 September, 19:14 in Dallas (timezoneId in the config).
const HERO_TIME = new Date('2026-09-23T19:14:00-05:00')

// Every §4.3 route, the specimen, and a mistyped path.
const ROUTES = [
  '/next/live',
  '/next/live/put?zone=living&look=embers',
  '/next/live/zones/living',
  '/next/looks?cat=calm&q=fire',
  '/next/looks/fireflies',
  '/next/map',
  '/next/map/tube',
  '/next/devices',
  '/next/devices/tube',
  '/next/inputs',
  '/next/settings#backup',
  '/next/system',
  '/next/lookz',
]

// Every product page. /next/system is a specimen, and some of its rows are wider than a phone.
const PAGES = ROUTES.filter((path) => path !== '/next/system')

async function open(page: Page, path: string) {
  await page.goto(path)
  await page.evaluate(() => document.fonts.ready)
}

/** axe's findings for the page as it stands, one line per rule. */
async function axeViolations(page: Page): Promise<string[]> {
  const { violations } = await new AxeBuilder({ page }).analyze()
  return violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)
}

/** How far a Tempo group's children reach past its right edge; 0 or less means TAP stays inside. */
function spill(group: Locator): Promise<number> {
  return group.evaluate((element) => {
    const rights = [...element.children].map((child) => child.getBoundingClientRect().right)
    return Math.max(...rights) - element.getBoundingClientRect().right
  })
}

test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(HERO_TIME)
})

// Done when (spec §13.1 M0): the chrome matches Main.png at 1440 × 900 and Phone-Live.png at 390 × 844.
test('Live chrome', async ({ page }) => {
  await open(page, '/next/live')
  await expect(page).toHaveScreenshot('live.png')
})

for (const path of ROUTES) {
  test(`axe passes on ${path}`, async ({ page }) => {
    await open(page, path)
    await expect(page.locator('h1')).toBeVisible()
    expect(await axeViolations(page)).toEqual([])
  })
}

// Decision 12: /system is there to run axe over every primitive. Base UI mounts an overlay's popup
// only while it's open, so each one is opened before axe looks.
const OVERLAYS: { name: string; open: (page: Page) => Promise<void>; popup: (page: Page) => Locator }[] = [
  {
    name: 'Tooltip',
    open: (page) => page.getByRole('button', { name: 'Fit', exact: true }).hover(),
    popup: (page) => page.getByText('Fit the home', { exact: true }),
  },
  {
    name: 'Popover',
    open: (page) => page.getByRole('button', { name: 'Popover', exact: true }).click(),
    popup: (page) => page.getByRole('dialog', { name: 'Needs attention', exact: true }),
  },
  {
    name: 'Dialog',
    open: (page) => page.getByRole('button', { name: 'Dialog', exact: true }).click(),
    popup: (page) => page.getByRole('dialog', { name: 'Restore from a file', exact: true }),
  },
  {
    name: 'Sheet',
    open: (page) => page.getByRole('button', { name: 'Sheet', exact: true }).click(),
    popup: (page) => page.getByRole('dialog', { name: 'Put a look on', exact: true }),
  },
  {
    name: 'Select',
    open: (page) => page.getByRole('combobox', { name: 'Transition', exact: true }).click(),
    popup: (page) => page.getByRole('listbox'),
  },
]

for (const overlay of OVERLAYS) {
  test(`axe passes with the ${overlay.name} open`, async ({ page }) => {
    await open(page, '/next/system')
    await overlay.open(page)
    await expect(overlay.popup(page)).toBeVisible()
    expect(await axeViolations(page)).toEqual([])
  })
}

test('fonts are self-hosted and load', async ({ page, baseURL }) => {
  const elsewhere: string[] = []
  page.on('request', (request) => {
    if (!request.url().startsWith(`${baseURL}/`)) elsewhere.push(request.url())
  })
  await open(page, '/next/live')
  expect(elsewhere).toEqual([])
  const loaded = await page.evaluate(() =>
    [...document.fonts].filter((face) => face.status === 'loaded').map((face) => face.family.replaceAll('"', '')),
  )
  expect(new Set(loaded)).toEqual(new Set(['Instrument Sans', 'Instrument Serif', 'JetBrains Mono Variable']))
})

// The rail and the specimen are desktop chrome, and a test that sets the width itself needs only
// one project.
test.describe('desktop', () => {
  test.skip(({ isMobile }) => isMobile)

  // §6.1 primitives and §6.2 cluster, laid out like System.png. The specimen fits one desktop
  // screen; on a phone the page scrolls inside <main>, so a screenshot would show only its top
  // (axe checks the whole phone page above).
  test('System specimen', async ({ page }) => {
    await open(page, '/next/system')
    await expect(page.getByText('Always within reach')).toBeVisible()
    await expect(page).toHaveScreenshot('system.png')
  })

  test('the keyboard walks the rail, then the cluster', async ({ page }) => {
    await open(page, '/next/live')
    const names: string[] = []
    for (let i = 0; i < 11; i += 1) {
      await page.keyboard.press('Tab')
      names.push(await page.evaluate(() => {
        const el = document.activeElement
        return el?.getAttribute('aria-label') ?? el?.textContent?.trim() ?? ''
      }))
    }
    expect(names).toEqual([
      'dj-ledfx home',
      'Live',
      'Looks',
      'Map',
      'Devices, needs attention',
      'Inputs',
      'Settings',
      'Music',
      'Tap',
      'Preview only',
      '1 needs attention',
    ])
    for (let i = 0; i < 4; i += 1) await page.keyboard.press('Shift+Tab')
    await expect(page.getByRole('link', { name: 'Settings' })).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/\/next\/settings$/)
    await expect(page.getByRole('heading', { level: 1, name: 'Settings' })).toBeVisible()
  })

  // Review focus: crossing 768 px (a window resize, a tablet rotating) swaps the chrome in place.
  test('resizing across 768 px swaps the chrome without a reload', async ({ page }) => {
    await open(page, '/next/live')
    await page.evaluate(() => Object.assign(window, { stillHere: true }))
    await page.setViewportSize({ width: 767, height: 900 })
    await expect(page.getByRole('link', { name: 'Tempo' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'dj-ledfx home' })).toHaveCount(0)
    await page.setViewportSize({ width: 768, height: 900 })
    await expect(page.getByRole('link', { name: 'dj-ledfx home' })).toBeVisible()
    expect(await page.evaluate(() => 'stillHere' in window)).toBe(true)
  })

  for (const width of [320, 360, 390, 768, 1024, 1199, 1440]) {
    test(`nothing scrolls sideways at ${width} px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      for (const path of PAGES) {
        await open(page, path)
        await expect(page.locator('h1')).toBeVisible()
        // <main> scrolls by itself (overflow-y: auto makes overflow-x auto too), so the document's
        // width alone can't see a page that's wider than <main>.
        const [documentWidth, mainOverflow] = await page.evaluate(() => {
          const main = document.querySelector('main')!
          return [document.documentElement.scrollWidth, main.scrollWidth - main.clientWidth]
        })
        expect(documentWidth, `${path}: the document`).toBeLessThanOrEqual(width)
        expect(mainOverflow, `${path}: <main>`).toBeLessThanOrEqual(0)
      }
      if (width < 768) {
        await open(page, '/next/live')
        // The phone tempo strip is fluid: TAP must stay inside it down to 320 px (WCAG reflow).
        expect(await spill(page.getByRole('group', { name: 'Tempo' }))).toBeLessThanOrEqual(0)
      }
    })
  }

  // The hero's "Music" is the shortest source label. The specimen draws the longer ones, a
  // three-digit bar, and the strip at a 320 px phone's width; TAP stays inside every one.
  test('the tempo module keeps TAP inside, whatever the source', async ({ page }) => {
    await open(page, '/next/system')
    await expect(page.getByText('Always within reach')).toBeVisible()
    const groups = await page.getByRole('group', { name: 'Tempo' }).all()
    expect(groups).toHaveLength(7) // the top bar's, and the specimen's three bars and three strips
    for (const [i, group] of groups.entries()) {
      expect(await spill(group), `Tempo group ${i + 1}`).toBeLessThanOrEqual(0)
    }
  })
})

// Touch targets and a phone turned sideways are phone matters.
test.describe('phone', () => {
  test.skip(({ isMobile }) => !isMobile)

  // §6: touch targets are at least 44 px on phone. TAP keeps Phone-Live.png's 40 px face, and its
  // hit area fills a 44 px band centred on it.
  test('TAP answers a touch anywhere in a 44 px band on phone', async ({ page }) => {
    await open(page, '/next/live')
    const box = await page.getByRole('group', { name: 'Tempo' }).getByRole('button', { name: 'Tap' }).boundingBox()
    if (!box) throw new Error('TAP is not on screen')
    const [x, middle] = [box.x + box.width / 2, box.y + box.height / 2]
    const hits = await page.evaluate(
      (points) => points.map(([px, py]) => document.elementFromPoint(px, py)?.closest('button')?.textContent ?? null),
      [
        [x, middle - 21.5],
        [x, middle + 21.5],
      ],
    )
    expect(hits).toEqual(['Tap', 'Tap'])
  })

  // A phone turned sideways (844 × 390) is wider than 768 px, so it gets the rail and the top bar,
  // with the notch on one side (viewport-fit=cover). Chromium's safe-area override stands in for it.
  test('a landscape phone keeps the rail reachable and clear of the notch', async ({ page }) => {
    const [width, height, notch] = [844, 390, 47]
    await page.setViewportSize({ width, height })
    const cdp = await page.context().newCDPSession(page)
    await cdp.send('Emulation.setSafeAreaInsetsOverride', { insets: { top: 0, left: notch, right: notch, bottom: 21 } })
    await open(page, '/next/live')

    // The page itself never scrolls; the rail and <main> scroll by themselves.
    expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBeLessThanOrEqual(height)
    const rail = page.getByRole('navigation', { name: 'Main' })
    const settings = rail.getByRole('link', { name: 'Settings' })
    await settings.scrollIntoViewIfNeeded()
    await expect(settings).toBeInViewport({ ratio: 1 })
    for (const link of await rail.getByRole('link').all()) {
      const box = (await link.boundingBox())!
      expect(box.x, 'clear of the left inset').toBeGreaterThanOrEqual(notch)
      expect(box.height, 'still a whole target').toBeGreaterThanOrEqual(44)
    }

    // The rail's column grows with it, so the top bar starts where the rail ends.
    const railBox = (await rail.boundingBox())!
    expect((await page.getByRole('banner').boundingBox())!.x).toBe(railBox.x + railBox.width)

    // The top bar's cluster and the page stop short of the right inset.
    const reach = await page
      .getByRole('banner')
      .evaluate((bar) => Math.max(...[...bar.querySelectorAll('*')].map((el) => el.getBoundingClientRect().right)))
    expect(reach, 'the top bar clears the right inset').toBeLessThanOrEqual(width - notch)
    expect(await page.locator('main').evaluate((main) => getComputedStyle(main).paddingRight)).toBe(`${notch}px`)
  })
})
