import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

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

async function open(page: Page, path: string) {
  await page.goto(path)
  await page.evaluate(() => document.fonts.ready)
}

test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(HERO_TIME)
})

// Done when (spec §13.1 M0): the chrome matches Main.png at 1440 × 900 and Phone-Live.png at 390 × 844.
test('Live chrome', async ({ page }) => {
  await open(page, '/next/live')
  await expect(page).toHaveScreenshot('live.png')
})

// §6.1 primitives and §6.2 cluster, laid out like System.png. The phone page scrolls inside <main>,
// so a phone screenshot would show only its top; axe still checks the whole phone page below.
test('System specimen', async ({ page }, { project }) => {
  test.skip(project.name !== 'desktop', 'the specimen fits one desktop screen')
  await open(page, '/next/system')
  await expect(page.getByText('Always within reach')).toBeVisible()
  await expect(page).toHaveScreenshot('system.png')
})

for (const path of ROUTES) {
  test(`axe passes on ${path}`, async ({ page }) => {
    await open(page, path)
    await expect(page.locator('h1')).toBeVisible()
    const { violations } = await new AxeBuilder({ page }).analyze()
    expect(violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([])
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

test('the keyboard walks the rail, then the cluster', async ({ page }, { project }) => {
  test.skip(project.name !== 'desktop', 'the rail is desktop chrome')
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
test('resizing across 768 px swaps the chrome without a reload', async ({ page }, { project }) => {
  test.skip(project.name !== 'desktop', 'one project is enough; this test sets the width')
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
  test(`nothing scrolls sideways at ${width} px`, async ({ page }, { project }) => {
    test.skip(project.name !== 'desktop', 'one project is enough; this test sets the width')
    await page.setViewportSize({ width, height: 900 })
    await open(page, '/next/live')
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    if (width < 768) {
      // The phone tempo strip is fluid: TAP must stay inside it down to 320 px (WCAG reflow).
      const spill = await page.getByRole('group', { name: 'Tempo' }).evaluate((group) => {
        const rights = [...group.children].map((child) => child.getBoundingClientRect().right)
        return Math.max(...rights) - group.getBoundingClientRect().right
      })
      expect(spill).toBeLessThanOrEqual(0)
    }
  })
}
