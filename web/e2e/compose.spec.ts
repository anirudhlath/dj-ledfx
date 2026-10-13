import { expect, test, type Locator, type Page } from '@playwright/test'
import { LIVE_SPEC } from '../src/design/live-numbers'
import { notch, open, stageCanvas, type Insets } from './helpers'

// The hero moment (spec §12.5): Wednesday 23 September, 19:14 in the home's time zone (timezoneId in the config).
const HERO_TIME = new Date('2026-09-23T19:14:00-05:00')

/** The path with ?still: the mock holds the beat and the frames, so a screenshot is the same every run. */
const still = (path: string) => `${path}&still`

/** An element's box, which must be on screen. */
async function box(locator: Locator) {
  const found = await locator.boundingBox()
  if (!found) throw new Error(`${locator} is not on screen`)
  return found
}

/** Layout's rounding: a fraction of a pixel is neither a cut ring, nor a scroll, nor a hit band short of --touch-min. */
const SLACK = 0.5

/**
 * Phone-PutLookOn's sheet lies this far up over the stage's foot, and pads this far under Start. The render's HTML sets both (a -36px margin
 * and a 30px bottom padding) and `design:numbers` generates neither, so they are written here, once, for the measurements to compare with.
 */
const PHONE_SHEET_OVERLAP_PX = 36
const PHONE_FOOTER_PAD_PX = 30

/** How far <main> can scroll (what its content has beyond its box), and the offset it is scrolled to: the composer's pages fit it, so neither is ever more than 0. */
function mainScroll(page: Page) {
  return page.locator('main').evaluate((main) => ({ beyond: main.scrollHeight - main.clientHeight, at: main.scrollTop }))
}

/** Waits until nothing on the page scrolls any more: every element's offsets are the same for five frames running. */
function settled(page: Page): Promise<void> {
  return page.evaluate(
    () =>
      new Promise<void>((resolve) => {
        const offsets = () => Array.from(document.querySelectorAll('*'), (element) => `${element.scrollLeft},${element.scrollTop}`).join(' ')
        let last = offsets()
        let still = 0
        const frame = () => {
          const now = offsets()
          still = now === last ? still + 1 : 0
          last = now
          if (still >= 5) resolve()
          else requestAnimationFrame(frame)
        }
        requestAnimationFrame(frame)
      }),
  )
}

/** The composer gives the chosen look's tile or row the focus as it opens (F4 ruling 12): waits for that, so no focus of its own comes after the test's. */
function opened(page: Page) {
  return expect(page.getByRole('group', { name: 'Looks' }).locator('[data-look][tabindex="0"]')).toBeFocused()
}

/** An element's box once it has stopped moving: two reads in a row agree. */
async function restingBox(locator: Locator) {
  let before = ''
  await expect
    .poll(async () => {
      const now = JSON.stringify(await locator.boundingBox())
      const rest = now === before
      before = now
      return rest
    })
    .toBe(true)
  return box(locator)
}

/**
 * Whether the focused element's ring is whole: how far it reaches past the nearest ancestor that clips it (the viewport, where none does),
 * side by side. A ring reaches its outline's width and offset beyond the element (tokens.css); 0 or less on every side is a whole ring.
 * The page must have settled.
 */
async function expectRingWhole(page: Page, what: string) {
  await settled(page)
  const { ring, past } = await page.evaluate(() => {
    const element = document.activeElement
    if (!(element instanceof HTMLElement)) throw new Error('nothing has the focus')
    const style = getComputedStyle(element)
    if (style.outlineStyle === 'none') throw new Error(`${element.tagName} draws no focus ring`)
    const reach = parseFloat(style.outlineWidth) + parseFloat(style.outlineOffset)
    let clip: Element | null = element.parentElement
    while (clip && clip !== document.documentElement) {
      const { overflowX, overflowY } = getComputedStyle(clip)
      if (overflowX !== 'visible' || overflowY !== 'visible') break
      clip = clip.parentElement
    }
    let port = { left: 0, top: 0, right: innerWidth, bottom: innerHeight }
    if (clip && clip !== document.documentElement) {
      // The scrollport: the box inside the clipper's border, and inside its scrollbar.
      const edge = clip.getBoundingClientRect()
      const left = edge.left + clip.clientLeft
      const top = edge.top + clip.clientTop
      port = { left, top, right: left + clip.clientWidth, bottom: top + clip.clientHeight }
    }
    const own = element.getBoundingClientRect()
    return {
      ring: reach,
      past: { left: port.left - (own.left - reach), right: own.right + reach - port.right, top: port.top - (own.top - reach), bottom: own.bottom + reach - port.bottom },
    }
  })
  expect(Math.max(...Object.values(past)), `${what}: its ${ring} px ring reaches past the clip by ${JSON.stringify(past)}`).toBeLessThanOrEqual(SLACK)
}

/**
 * The controls under `scope` drawn shorter than --touch-min, each with the height of its hit band once the boxes that clip it are taken off.
 * A control draws its band with `touch-target` (its ::before reaches past its box), on itself or on the label that holds it; one with none
 * has its own box. The band is the ::before's, which getComputedStyle gives in px.
 */
function shortControls(scope: Locator) {
  return scope.evaluate((root) => {
    const minimum = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--touch-min'))
    const found: { control: string; drawn: number; band: number; minimum: number }[] = []
    const controls = root.querySelectorAll<HTMLElement>('button, a[href], input, select, textarea, [role="combobox"], [role="button"], [role="switch"], [role="option"]')
    for (const control of controls) {
      if (control.getAttribute('aria-hidden') === 'true') continue
      const host = control.closest<HTMLElement>('.touch-target') ?? control
      const face = host.getBoundingClientRect()
      if (face.height < 1 || face.height >= minimum) continue
      let top = face.top
      let height = face.height
      if (host.classList.contains('touch-target')) {
        const band = getComputedStyle(host, '::before')
        top = face.top + host.clientTop + parseFloat(band.top)
        height = parseFloat(band.height)
      }
      let bottom = top + height
      for (let around = host.parentElement; around; around = around.parentElement) {
        const { overflowX, overflowY } = getComputedStyle(around)
        if (overflowX === 'visible' && overflowY === 'visible') continue
        const edge = around.getBoundingClientRect()
        top = Math.max(top, edge.top + around.clientTop)
        bottom = Math.min(bottom, edge.top + around.clientTop + around.clientHeight)
      }
      const name = control.getAttribute('aria-label') ?? control.textContent?.trim() ?? control.tagName
      found.push({ control: `${control.tagName.toLowerCase()} ${name.slice(0, 24)}`, drawn: face.height, band: Math.max(0, bottom - top), minimum })
    }
    return found
  })
}

interface State {
  /** The screenshot's name; Playwright adds the project's. */
  name: string
  path: string
  /** The render its baseline is compared with by eye, the project's own; null for a state no render draws. */
  render: 'PutLookOn' | null
  /** What shows once the state is drawn. */
  ready: (page: Page) => Locator
  /** Brings the state about once the page is open. */
  then?: (page: Page) => Promise<void>
  /** Desktop only: the phone's composer has no search (Phone-PutLookOn). */
  desktop?: true
}

// §13.1 F4: Put a look on, in each state the composer has, on both sizes. Names come from the mock, so
// none is written here: the ids are in the paths, and what's waited for is the composer's own words.
const STATES: State[] = [
  // Live-PutLookOn and Phone-PutLookOn: a look previewed on a room that runs another.
  { name: 'preview', path: '/next/live/put?zone=living&look=embers', render: 'PutLookOn', ready: (page) => page.getByText(/^Preview on screen/) },
  { name: 'no-look', path: '/next/live/put?zone=living', render: null, ready: (page) => page.getByText('Choose a look to see it on the stage first.') },
  {
    name: 'waits-for-music',
    path: '/next/live/put?scenario=dj-playing&zone=living&look=spectrum',
    render: null,
    ready: (page) => page.getByText('Waits for music', { exact: true }).first(),
  },
  // §8.2: a home look locks the zone to the whole home; with Home Assistant down, it would wait for it.
  {
    name: 'home-look',
    path: '/next/live/put?scenario=inputs-down&zone=living&look=goodnight',
    render: null,
    ready: (page) => page.getByText('Needs Home Assistant', { exact: true }).first(),
  },
  { name: 'no-lights', path: '/next/live/put?zone=counter&look=embers', render: null, ready: (page) => page.getByText(/ has no lights\.$/) },
  {
    name: 'no-match',
    path: '/next/live/put?zone=living&look=embers',
    render: null,
    ready: (page) => page.getByText(/^Preview on screen/),
    then: async (page) => {
      await page.getByRole('searchbox', { name: 'Search looks' }).fill('zzzz')
      await expect(page.getByText('No looks match “zzzz”.')).toBeVisible()
    },
    desktop: true,
  },
]

test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(HERO_TIME)
})

for (const size of ['desktop', 'phone'] as const) {
  test.describe(`Put a look on's states on ${size === 'desktop' ? 'desktop' : 'the phone'}`, () => {
    test.skip(({ isMobile }) => isMobile !== (size === 'phone'))

    for (const state of STATES.filter((each) => size === 'desktop' || each.desktop !== true)) {
      test(`${state.name}${state.render === null ? '' : `, as ${size === 'desktop' ? 'Live' : 'Phone'}-${state.render}`}`, async ({ page }) => {
        await open(page, still(state.path))
        await expect(stageCanvas(page)).toBeVisible()
        await expect(state.ready(page)).toBeVisible()
        // As live.spec.ts: on desktop, the banner's frame rate settled.
        if (size === 'desktop') await expect(page.getByRole('banner').getByText('60 fps')).toBeVisible({ timeout: 10_000 })
        await state.then?.(page)
        // The composer gives a look the focus as it opens (F4 ruling 12), and a page opened by its URL
        // rings it as a keyboard would; the renders draw the page at rest.
        await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur())
        await expect(page).toHaveScreenshot(`${state.name}.png`)
      })
    }
  })
}

// A scroller clips an absolutely positioned element only if the element's containing block (its nearest positioned ancestor) is inside the
// scroller. With the holder outside, the element is neither clipped nor scrolled with it, and a hidden label (sr-only) that way stretched
// <main>'s scroll area by its place: the Running panel's slider labels and a transition's "from" and "to" did, by 27 to 39 px on a short screen
// (the Running panel's test, below). It happens at any height, so this finds the element itself, wherever it is in <main>: none may escape a clip.
for (const [name, path, ready] of [
  ['Live', '/next/live?scenario=transition&still', (page: Page) => page.getByRole('slider').first()],
  ['Live, with a problem', '/next/live?scenario=problems&still', (page: Page) => page.getByRole('slider').first()],
  ['Put a look on', '/next/live/put?zone=living&look=embers&still', (page: Page) => page.getByRole('group', { name: 'Categories' })],
  ['Zone detail', '/next/live/zones/living?scenario=transition&still', (page: Page) => page.getByRole('slider').first()],
] as const) {
  test(`${name}: nothing absolutely positioned in <main> escapes a clip`, async ({ page }) => {
    await open(page, path, stageCanvas(page))
    await expect(ready(page)).toBeVisible()
    await settled(page)
    const { examined, escaped } = await page.locator('main').evaluate((main) => {
      const clips = (element: Element) => {
        const { overflowX, overflowY } = getComputedStyle(element)
        return overflowX !== 'visible' || overflowY !== 'visible'
      }
      /** Whether an element is the containing block of what it holds that is absolutely positioned: positioned, or a transform or the like. */
      const holds = (element: Element) => {
        const style = getComputedStyle(element)
        return style.position !== 'static' || style.transform !== 'none' || style.perspective !== 'none' || style.filter !== 'none' || /layout|paint|strict|content/.test(style.contain)
      }
      let examined = 0
      const escaped: string[] = []
      for (const element of main.querySelectorAll('*')) {
        if (getComputedStyle(element).position !== 'absolute' || element.getClientRects().length === 0) continue
        examined++
        const clippers: string[] = []
        for (let up = element.parentElement; up && !holds(up); up = up.parentElement) {
          if (clips(up)) clippers.push(`${up.tagName.toLowerCase()}.${up.getAttribute('class')?.slice(0, 30) ?? ''}`)
        }
        if (clippers.length > 0) {
          escaped.push(`${element.tagName.toLowerCase()}.${element.getAttribute('class')?.slice(0, 30) ?? ''} "${(element.textContent ?? '').slice(0, 20)}" escapes ${clippers.join(' > ')}`)
        }
      }
      return { examined, escaped }
    })
    expect(examined, 'absolutely positioned elements looked at, or this checks nothing').toBeGreaterThan(0)
    expect(escaped).toEqual([])
  })
}

test.describe('on desktop', () => {
  test.skip(({ isMobile }) => isMobile)

  // F4 ruling 12: L opens the composer on the first look; the arrows choose as they move; Enter starts the
  // look chosen, and Esc leaves.
  test('the keyboard puts a look on: L, the arrows and Enter', async ({ page }) => {
    await open(page, '/next/live')
    await page.keyboard.press('l')
    await expect(page).toHaveURL(/\/next\/live\/put$/)
    const tiles = page.getByRole('group', { name: 'Looks' }).locator('[data-look]')
    await expect(tiles.first()).toBeFocused()
    await page.keyboard.press('ArrowRight')
    await expect(tiles.nth(1)).toBeFocused()
    await expect(page).toHaveURL(new RegExp(`look=${await tiles.nth(1).getAttribute('data-look')}$`))
    await expect(tiles.nth(1)).toHaveAttribute('aria-pressed', 'true')
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/\/next\/live$/)
    await expect(page.getByRole('status')).toHaveText(/^Started .+ on .+\.$/)

    await page.keyboard.press('l')
    await expect(tiles.first()).toBeFocused()
    await page.keyboard.press('Escape')
    await expect(page).toHaveURL(/\/next\/live$/)
  })

  // §6.4's composer tiles, to the pixel: the panel's border leaves each of the grid's two columns half a
  // pixel short, as the render's own grid does.
  test('the tiles are as wide as §6.4 says', async ({ page }) => {
    await open(page, '/next/live/put?zone=living&look=embers')
    const tiles = page.getByRole('group', { name: 'Looks' }).locator('[data-look]')
    await expect(tiles.first()).toBeVisible()
    for (const tile of await tiles.all()) {
      expect(Math.round((await box(tile)).width)).toBe(LIVE_SPEC.lookTile.px)
    }
  })

  // The composer's page fits <main>, which never scrolls: Live's page is <main>'s own height, and the panel's grid takes what its header and
  // footer leave. 1000 px is §4.4's narrow layout, where the composer lies over the stage.
  for (const [width, height] of [
    [1440, 900],
    [1280, 720],
    [1000, 800],
  ]) {
    test(`the composer fits ${width} x ${height}: <main> doesn't scroll and Start is on screen`, async ({ page }) => {
      await page.setViewportSize({ width, height })
      await open(page, still('/next/live/put?zone=living&look=embers'))
      const start = page.getByRole('complementary', { name: 'Put a look on' }).getByRole('button', { name: /^Start/ })
      await expect(start).toBeVisible()
      expect(await mainScroll(page)).toEqual({ beyond: 0, at: 0 })
      const place = await box(start)
      expect(place.y).toBeGreaterThanOrEqual(0)
      expect(place.y + place.height).toBeLessThanOrEqual(height)
    })
  }

  // The Running panel's list scrolls when its cards don't fit, and what is hidden in a card (a slider's label, a transition's "from" and "to")
  // is positioned by the card, not by <main>: with no positioned ancestor inside the list it escaped the list's clip and stretched <main>'s
  // scroll area (measured before the fix: 27 px at 1440 x 400, 39 px at 844 x 390).
  for (const [scenario, width, height] of [
    ['problems', 1440, 350],
    ['doorbell', 1440, 400],
    ['transition', 1440, 400],
    ['doorbell', 844, 390],
    ['problems', 844, 390],
  ] as const) {
    test(`Live's Running panel scrolls at ${width} x ${height} (${scenario}), and <main> doesn't`, async ({ page }) => {
      await page.setViewportSize({ width, height })
      await open(page, `/next/live?scenario=${scenario}&still`)
      await expect(stageCanvas(page)).toBeVisible()
      const panel = page.getByRole('complementary', { name: 'Running' })
      await expect(panel).toBeVisible()
      // The premise: the cards have come in and the panel's list scrolls.
      await expect
        .poll(
          () =>
            panel.evaluate((aside) => {
              const list = [...aside.querySelectorAll('div')].find((each) => getComputedStyle(each).overflowY === 'auto')
              return list === undefined ? null : list.scrollHeight - list.clientHeight
            }),
          { message: "the panel's list overflows, or this checks nothing" },
        )
        .toBeGreaterThan(0)
      await settled(page)
      expect(await mainScroll(page)).toEqual({ beyond: 0, at: 0 })
    })
  }

  // F4 ruling 12 and §14: Tab reaches the category row. It clips (its last chip is cut at the panel's edge, as drawn), and the browser leaves
  // a chip that is 32 px or more in view where it is, which cut the last chip's ring by 45 px at 1440 x 900: a chip the keyboard focuses
  // is scrolled in with the room its ring needs, and the row goes back to its start once focus leaves, as nothing else can scroll it back.
  test('Tab walks the category chips with every ring whole, and the row goes back to its start when focus leaves', async ({ page }) => {
    await open(page, still('/next/live/put?zone=living&look=embers'))
    const row = page.getByRole('group', { name: 'Categories' })
    const chips = row.getByRole('button')
    await expect(chips.first()).toBeVisible()
    await opened(page)
    const count = await chips.count()
    const offset = () => row.evaluate((element) => element.scrollLeft)
    expect(await row.evaluate((element) => element.scrollWidth - element.clientWidth), 'the row clips its last chip, as drawn').toBeGreaterThan(0)

    await page.getByRole('searchbox', { name: 'Search looks' }).focus()
    for (let at = 0; at < count; at++) {
      await page.keyboard.press('Tab')
      await expect(chips.nth(at)).toBeFocused()
      await expectRingWhole(page, `chip ${at + 1} of ${count}`)
    }
    expect(await offset(), 'the last chip was scrolled in').toBeGreaterThan(0)
    await page.keyboard.press('Tab')
    await expect(page.getByRole('group', { name: 'Looks' }).locator('[data-look][tabindex="0"]')).toBeFocused()
    expect(await offset()).toBe(0)

    // And back: Shift+Tab from the grid lands on the last chip, which is out of view again, then walks the row to the first.
    await page.keyboard.press('Shift+Tab')
    await expect(chips.nth(count - 1)).toBeFocused()
    await expectRingWhole(page, 'the last chip, from the grid')
    for (let at = count - 2; at >= 0; at--) {
      await page.keyboard.press('Shift+Tab')
      await expect(chips.nth(at)).toBeFocused()
      await expectRingWhole(page, `chip ${at + 1} of ${count}, going back`)
    }
    await page.keyboard.press('Shift+Tab')
    await expect(page.getByRole('searchbox', { name: 'Search looks' })).toBeFocused()
    expect(await offset()).toBe(0)
  })

  // The arrows move the focus through the tiles, and the grid scrolls to each; the browser scrolls a tile to the grid's edge, which cut its ring
  // by 3.5 px (scroll-py-1 leaves the room). Every tile on the way up, down and up again, the first and the last among them.
  test('the arrows walk the tiles with every ring whole', async ({ page }) => {
    await open(page, still('/next/live/put?zone=living&look=embers'))
    const grid = page.getByRole('group', { name: 'Looks' })
    const scroller = grid.locator('xpath=..')
    const focused = () => page.evaluate(() => (document.activeElement as HTMLElement).dataset.look)
    await opened(page)
    expect(await scroller.evaluate((element) => element.scrollHeight - element.clientHeight), 'the grid scrolls').toBeGreaterThan(0)

    /** Presses `key` until the focus stops moving, with every tile it reaches rung whole; returns the tiles reached. */
    async function walk(key: string) {
      const reached: string[] = []
      for (let step = 0; step < 40; step++) {
        const before = await focused()
        await page.keyboard.press(key)
        const after = await focused()
        if (after === before) return reached
        expect(after).toBeDefined()
        await expectRingWhole(page, `${key} to ${after}`)
        reached.push(after!)
      }
      throw new Error(`${key} never stopped`)
    }
    await walk('ArrowUp')
    await expect(grid.locator('[data-look]').first()).toBeFocused()
    expect(await scroller.evaluate((element) => element.scrollTop), 'at the top').toBe(0)
    const down = await walk('ArrowDown')
    expect(down.length, 'rows below').toBeGreaterThan(2)
    await walk('ArrowRight')
    await expect(grid.locator('[data-look]').last()).toBeFocused()
    expect((await walk('ArrowUp')).length, 'and back up').toBeGreaterThan(2)
    expect(await scroller.evaluate((element) => element.scrollTop), 'back at the top').toBe(0)
  })

  // The desktop's zone chips wrap along the top of the stage, so no row scrolls them; the first and the last, and "Pick lights…", keep their rings whole.
  test('Tab walks the zone chips with every ring whole', async ({ page }) => {
    await open(page, still('/next/live/put?zone=living&look=embers'))
    const chips = page.getByRole('group', { name: 'Where' }).getByRole('button')
    await expect(chips.first()).toBeVisible()
    await opened(page)
    const count = await chips.count()
    await chips.first().focus()
    await expectRingWhole(page, `zone chip 1 of ${count}`)
    for (let at = 1; at < count; at++) {
      await page.keyboard.press('Tab')
      await expect(chips.nth(at)).toBeFocused()
      await expectRingWhole(page, `zone chip ${at + 1} of ${count}`)
    }
  })

  // §6.3: "Pick lights…" is drawn but can't be used yet (F4 ruling 6), so it keeps the default cursor where every other button has a pointer.
  test('"Pick lights…" keeps the default cursor, and the zone chips have the pointer', async ({ page }) => {
    await open(page, still('/next/live/put?zone=living&look=embers'))
    const where = page.getByRole('group', { name: 'Where' })
    await expect(where.getByRole('button', { name: 'Pick lights…' })).toHaveCSS('cursor', 'default')
    await expect(where.getByRole('button', { name: 'Pick lights…' })).toHaveAttribute('aria-disabled', 'true')
    await expect(where.getByRole('button').first()).toHaveCSS('cursor', 'pointer')
  })

  // The search's whole face is its label: a click on its icon, its padding or the band touch-target grows past its edge focuses the input.
  test("a click anywhere on the search's face focuses its input", async ({ page }) => {
    await open(page, still('/next/live/put?zone=living&look=embers'))
    const input = page.getByRole('searchbox', { name: 'Search looks' })
    const face = await box(input.locator('xpath=ancestor::label'))
    const icon = await box(input.locator('xpath=preceding-sibling::*[local-name()="svg"]'))
    const middle = face.y + face.height / 2
    const points: [string, number, number][] = [
      ['its icon', icon.x + icon.width / 2, icon.y + icon.height / 2],
      ['its left padding', face.x + 3, middle],
      ['its right end', face.x + face.width - 3, middle],
      ['its top edge', face.x + face.width / 2, face.y + 2],
      ['its bottom edge', face.x + face.width / 2, face.y + face.height - 2],
      // The band reaches 3 px past the face. The category chips' own bands (8 px past their faces, 10 px below the search) take the last
      // pixel of it, so the probe sits just inside.
      ["the touch band's top", face.x + face.width / 2, face.y - 2],
      ["the touch band's bottom", face.x + face.width / 2, face.y + face.height + 1],
    ]
    for (const [where, x, y] of points) {
      await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur())
      await expect(input).not.toBeFocused()
      await page.mouse.click(x, y)
      await expect(input, `a click on ${where}`).toBeFocused()
    }
  })

  // Start is the panel's last row, so a longer consequence line (the grid gives up the room) moves nothing under it: its place is the same
  // for the line's one, two and three lines.
  test('Start stays where it is for a consequence of one, two and three lines', async ({ page }) => {
    const placed = new Map<number, number>()
    for (const [path, says] of [
      ['/next/live/put?zone=living', 'Choose a look to see it on the stage first.'],
      ['/next/live/put?zone=living&look=embers', 'will run'],
      ['/next/live/put?scenario=inputs-down&zone=living&look=goodnight', 'Waiting for Home Assistant'],
    ] as const) {
      await open(page, still(path))
      const panel = page.getByRole('complementary', { name: 'Put a look on' })
      const consequence = panel.locator('[data-consequence]')
      await expect(consequence).toContainText(says)
      const lines = await consequence.evaluate((element) => Math.round(element.getBoundingClientRect().height / parseFloat(getComputedStyle(element).lineHeight)))
      placed.set(lines, (await box(panel.getByRole('button', { name: /^Start/ }))).y)
    }
    expect([...placed.keys()], 'a consequence of one, two and three lines').toEqual([1, 2, 3])
    expect(new Set(placed.values()).size, `Start's y for each of them: ${JSON.stringify([...placed])}`).toBe(1)
  })

  // Every control drawn shorter than --touch-min has a hit band that tall (CLAUDE.md, touch-target), once the boxes that clip it are taken
  // off: the category row pads by the band's reach, the zone chips sit in the stage, the search's face is a label that grows.
  test('every control drawn shorter than --touch-min has a hit band that tall', async ({ page }) => {
    await open(page, still('/next/live/put?zone=living&look=embers'))
    await expect(page.getByRole('group', { name: 'Categories' }).getByRole('button').first()).toBeVisible()
    const short = [
      ...(await shortControls(page.getByRole('complementary', { name: 'Put a look on' }))),
      ...(await shortControls(page.getByRole('group', { name: 'Where' }))),
    ]
    expect(
      short.map(({ control }) => control),
      'the composer has controls under --touch-min, or this checks nothing',
    ).toEqual(expect.arrayContaining(['button Close', 'button Tempo', 'button Transition', 'button Pick lights…', 'input ']))
    expect(short.filter(({ band, minimum }) => band < minimum - SLACK)).toEqual([])
  })
})

test.describe('on the phone', () => {
  test.skip(({ isMobile }) => !isMobile)

  // §8.10's zone buttons and the look rows' thumbs, at the sizes it gives them (LIVE_SPEC.phoneComposer).
  test("the zone buttons and the rows' thumbs are §8.10's", async ({ page }) => {
    await open(page, '/next/live/put?zone=living&look=embers')
    const sheet = page.getByRole('region', { name: 'Put a look on' })
    const zones = sheet.getByRole('group', { name: 'Where' }).getByRole('button')
    await expect(zones.first()).toBeVisible()
    for (const zone of await zones.all()) {
      expect((await box(zone)).height).toBe(LIVE_SPEC.phoneComposer.zonePx)
    }
    const thumb = await box(sheet.locator('[data-look="embers"] [data-thumb]'))
    expect([thumb.width, thumb.height]).toEqual([LIVE_SPEC.phoneComposer.thumb.width, LIVE_SPEC.phoneComposer.thumb.height])
  })

  // The category chips keep Phone-PutLookOn's face, drawn smaller than --touch-min, and `touch-target` grows
  // each one's hit area to a band that tall (CLAUDE.md), inside the row that scrolls them.
  test('a category chip answers a touch anywhere in a band --touch-min tall', async ({ page }) => {
    await open(page, '/next/live/put?zone=living&look=embers')
    const chip = page.getByRole('group', { name: 'Categories' }).getByRole('button', { name: 'Tempo' })
    const face = await box(chip)
    const hits = await page.evaluate(
      ({ x, middle }) => {
        // Half a pixel inside the band's top and bottom edges.
        const reach = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--touch-min')) / 2 - 0.5
        return [middle - reach, middle + reach].map((y) => document.elementFromPoint(x, y)?.closest('button')?.textContent ?? null)
      },
      { x: face.x + face.width / 2, middle: face.y + face.height / 2 },
    )
    expect(hits).toEqual(['Tempo', 'Tempo'])
  })

  // F4 ruling 16: the page gives the sheet the screen under the stage, so only the look list scrolls, and a screen too short for a whole row
  // of it (about 670 px at 390 wide, 660 at 375) scrolls the sheet. <main> never does; the list always holds a whole row; Start can be
  // reached; and the sheet lies over the stage's foot as drawn, with the render's padding under Start and the notch's inset below that.
  const SCREENS: { width: number; height: number; insets?: Insets }[] = [
    { width: 390, height: 844 },
    { width: 390, height: 844, insets: { top: 47, right: 0, bottom: 34, left: 0 } },
    { width: 390, height: 664 },
    { width: 375, height: 667 },
    { width: 375, height: 548 },
  ]
  const named = ({ width, height, insets }: (typeof SCREENS)[number]) => `${width} x ${height}${insets === undefined ? '' : ' with a notch'}`

  for (const screen of SCREENS) {
    test(`the sheet at ${named(screen)}: <main> stays still, a whole look shows, Start can be reached and the sheet lies as drawn`, async ({ page }) => {
      await page.setViewportSize({ width: screen.width, height: screen.height })
      if (screen.insets !== undefined) await notch(page, screen.insets)
      const below = screen.insets?.bottom ?? 0
      await open(page, still('/next/live/put?zone=living&look=embers'))
      const sheet = page.getByRole('region', { name: 'Put a look on' })
      const start = sheet.getByRole('button', { name: /^Start/ })
      await expect(start).toBeVisible()
      await settled(page)
      expect(await mainScroll(page), '<main>').toEqual({ beyond: 0, at: 0 })

      // The list holds at least one whole row, measured against the first row's own height, not the constant the code floors it at.
      const list = await sheet.getByRole('group', { name: 'Looks' }).evaluate((element) => {
        const style = getComputedStyle(element)
        const port = element.getBoundingClientRect()
        const rows = [...element.querySelectorAll('[data-look]')].map((row) => row.getBoundingClientRect())
        return {
          content: element.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom),
          row: rows[0]!.height,
          whole: rows.filter((row) => row.top >= port.top - 0.5 && row.bottom <= port.bottom + 0.5).length,
        }
      })
      expect(list.content, "the list's room beside one row").toBeGreaterThanOrEqual(list.row)
      expect(list.whole, 'whole rows in the list').toBeGreaterThanOrEqual(1)

      // The sheet lies over the stage's foot. Taller than it needs, it doesn't scroll at all.
      const stage = await box(page.getByRole('region', { name: 'Home, live' }))
      const top = (await box(sheet)).y
      expect(stage.y + stage.height - top, "the sheet's overlap with the stage").toBeCloseTo(PHONE_SHEET_OVERLAP_PX, 0)
      const scrolls = await sheet.evaluate((element) => element.scrollHeight - element.clientHeight)
      if (screen.height >= 844) expect(scrolls, 'the sheet, on a screen this tall').toBe(0)

      // Start is on screen at the end of the sheet's scroll, with the render's padding under it and the notch's inset below that.
      await sheet.evaluate((element) => (element.scrollTop = element.scrollHeight))
      await settled(page)
      const place = await box(start)
      expect(place.y, 'Start, from the top').toBeGreaterThanOrEqual(screen.insets?.top ?? 0)
      expect(screen.height - (place.y + place.height), 'from the foot of the screen to Start').toBeCloseTo(PHONE_FOOTER_PAD_PX + below, 0)
      expect(await start.locator('xpath=..').evaluate((footer) => parseFloat(getComputedStyle(footer).paddingBottom)), "the footer's padding").toBe(PHONE_FOOTER_PAD_PX)
      expect(await mainScroll(page), '<main>, with the sheet scrolled to its end').toEqual({ beyond: 0, at: 0 })
    })

    // The transition list is a popup of the page, positioned beside its trigger: it must stay on the screen, and must not scroll <main> to do it.
    test(`the transition list at ${named(screen)} stays on the screen and leaves <main> still`, async ({ page }) => {
      await page.setViewportSize({ width: screen.width, height: screen.height })
      if (screen.insets !== undefined) await notch(page, screen.insets)
      await open(page, still('/next/live/put?zone=living&look=embers'))
      await page.getByRole('region', { name: 'Put a look on' }).getByRole('combobox', { name: 'Transition' }).click()
      const list = page.getByRole('listbox')
      await expect(list).toBeVisible()
      const place = await restingBox(list)
      expect(place.x, 'left').toBeGreaterThanOrEqual(0)
      expect(place.y, 'top').toBeGreaterThanOrEqual(0)
      expect(place.x + place.width, 'right').toBeLessThanOrEqual(screen.width)
      expect(place.y + place.height, 'bottom').toBeLessThanOrEqual(screen.height)
      expect(await mainScroll(page), '<main>').toEqual({ beyond: 0, at: 0 })
    })
  }

  // The zone row scrolls on its own: it opens with the chosen zone at its start (as drawn) or, where the row ends first, as far along as it goes.
  for (const zone of ['bedroom', 'living', 'counter']) {
    test(`the zone row opens scrolled to the chosen zone (${zone})`, async ({ page }) => {
      await open(page, still(`/next/live/put?zone=${zone}&look=embers`))
      const row = page.getByRole('group', { name: 'Where' })
      const chosen = row.getByRole('button', { pressed: true })
      await expect(chosen).toBeVisible()
      await settled(page)
      const where = await row.evaluate((element) => {
        const pressed = element.querySelector('[aria-pressed="true"]')!.getBoundingClientRect()
        const port = element.getBoundingClientRect()
        const padding = parseFloat(getComputedStyle(element).scrollPaddingLeft)
        return {
          fromStart: pressed.left - (port.left + element.clientLeft + padding),
          inside: pressed.left >= port.left && pressed.right <= port.right,
          toEnd: element.scrollWidth - element.clientWidth - element.scrollLeft,
          scrolls: element.scrollWidth > element.clientWidth,
        }
      })
      expect(where.scrolls, 'the row scrolls, or this checks nothing').toBe(true)
      expect(where.inside, 'the chosen zone is whole in the row').toBe(true)
      expect(Math.abs(where.fromStart) <= 1 || where.toEnd <= 1, `at the row's start, or the row's end: ${JSON.stringify(where)}`).toBe(true)
    })
  }

  // A zone chosen later scrolls only as far as it must, and nothing scrolls it back: a button cut at the row's edge, touched where it shows,
  // is whole once the row has settled (the snap the row has stays out of the way).
  test('a zone chosen later is whole once the row has settled', async ({ page }) => {
    await open(page, still('/next/live/put?zone=home&look=embers'))
    const row = page.getByRole('group', { name: 'Where' })
    const buttons = row.getByRole('button')
    const count = await buttons.count()
    // The first button that is cut at the row's right edge.
    const cut = await row.evaluate((element) => {
      const port = element.getBoundingClientRect()
      return [...element.querySelectorAll('button')].findIndex((each) => each.getBoundingClientRect().right > port.right)
    })
    expect(cut, 'a button is cut by the row, or this checks nothing').toBeGreaterThan(0)
    // The tap lands on the part of it that shows, with no scroll beforehand: it is the choice that scrolls the row.
    const port = await box(row)
    const shown = await box(buttons.nth(cut))
    await page.touchscreen.tap((shown.x + port.x + port.width) / 2, shown.y + shown.height / 2)
    await expect(buttons.nth(cut)).toHaveAttribute('aria-pressed', 'true')
    await settled(page)
    const whole = await row.evaluate((element, index) => {
      const port = element.getBoundingClientRect()
      const button = element.querySelectorAll('button')[index]!.getBoundingClientRect()
      return { left: button.left - port.left, right: port.right - button.right }
    }, cut)
    expect(Math.min(whole.left, whole.right), `the chosen zone is whole in the row: ${JSON.stringify(whole)}`).toBeGreaterThanOrEqual(-SLACK)
    // And on to the last one, which is the row's end.
    await buttons.nth(count - 1).tap()
    await expect(buttons.nth(count - 1)).toHaveAttribute('aria-pressed', 'true')
    await settled(page)
    const last = await row.evaluate((element) => {
      const port = element.getBoundingClientRect()
      const button = [...element.querySelectorAll('button')].at(-1)!.getBoundingClientRect()
      return { left: button.left - port.left, right: port.right - button.right }
    })
    expect(Math.min(last.left, last.right), `the last zone is whole in the row: ${JSON.stringify(last)}`).toBeGreaterThanOrEqual(-SLACK)
  })

  // A home look locks the zone to the whole home, which moves the zone row to its first button: that scroll must not take <main> with it,
  // on a screen so short that the sheet itself scrolls too.
  for (const [width, height] of [
    [390, 844],
    [375, 548],
  ]) {
    test(`a home look moves the zone row to the whole home and leaves <main> still at ${width} x ${height}`, async ({ page }) => {
      await page.setViewportSize({ width, height })
      await open(page, still('/next/live/put?zone=living&look=embers'))
      const sheet = page.getByRole('region', { name: 'Put a look on' })
      const row = sheet.getByRole('group', { name: 'Where' })
      await expect(row.getByRole('button', { pressed: true })).toContainText('Living')
      await sheet.getByRole('group', { name: 'Categories' }).getByRole('button', { name: 'Home' }).tap()
      await sheet.locator('[data-look="goodnight"]').tap()
      await expect(sheet.locator('[data-look="goodnight"]')).toHaveAttribute('aria-pressed', 'true')
      await expect(row.getByRole('button', { pressed: true })).toContainText('Whole home')
      await settled(page)
      expect(await mainScroll(page), '<main>').toEqual({ beyond: 0, at: 0 })
      const whole = await row.evaluate((element) => {
        const port = element.getBoundingClientRect()
        const button = element.querySelector('[aria-pressed="true"]')!.getBoundingClientRect()
        return { left: button.left - port.left, right: port.right - button.right }
      })
      expect(Math.min(whole.left, whole.right), `the whole home is whole in the row: ${JSON.stringify(whole)}`).toBeGreaterThanOrEqual(-SLACK)
    })
  }

  // Tab walks the zone buttons, then the category chips: each row scrolls on its own and clips, and the browser leaves a button that is mostly in
  // view where it is, which cut a ring part-way along (the row's buttons) and at its end (the last). The first and the last of each are whole.
  test('Tab walks the zone buttons and the category chips with every ring whole', async ({ page }) => {
    await open(page, still('/next/live/put?zone=living&look=embers'))
    const sheet = page.getByRole('region', { name: 'Put a look on' })
    await expect(sheet.getByRole('group', { name: 'Categories' }).getByRole('button').first()).toBeVisible()
    await opened(page)
    await sheet.getByRole('button', { name: 'Close' }).focus()
    for (const [name, buttons] of [
      ['zone button', sheet.getByRole('group', { name: 'Where' }).getByRole('button')],
      ['category chip', sheet.getByRole('group', { name: 'Categories' }).getByRole('button')],
    ] as const) {
      const count = await buttons.count()
      for (let at = 0; at < count; at++) {
        await page.keyboard.press('Tab')
        await expect(buttons.nth(at)).toBeFocused()
        await expectRingWhole(page, `${name} ${at + 1} of ${count}`)
      }
    }
    // And back from the list: the last chip, out of view again, to the first zone button.
    await page.keyboard.press('Tab')
    await expect(sheet.getByRole('group', { name: 'Looks' }).locator('[data-look][tabindex="0"]')).toBeFocused()
    for (const [name, buttons] of [
      ['category chip', sheet.getByRole('group', { name: 'Categories' }).getByRole('button')],
      ['zone button', sheet.getByRole('group', { name: 'Where' }).getByRole('button')],
    ] as const) {
      for (let at = (await buttons.count()) - 1; at >= 0; at--) {
        await page.keyboard.press('Shift+Tab')
        await expect(buttons.nth(at)).toBeFocused()
        await expectRingWhole(page, `${name} ${at + 1}, going back`)
      }
    }
  })

  // Up and Down move through the rows, previewing each: the list scrolls to the row, and a ring is whole at the list's edges too.
  test('the arrows walk the rows with every ring whole', async ({ page }) => {
    await open(page, still('/next/live/put?zone=living&look=embers'))
    const list = page.getByRole('group', { name: 'Looks' })
    const focused = () => page.evaluate(() => (document.activeElement as HTMLElement).dataset.look)
    await opened(page)
    expect(await list.evaluate((element) => element.scrollHeight - element.clientHeight), 'the list scrolls').toBeGreaterThan(0)

    /** Presses `key` until the focus stops moving, with every row it reaches rung whole; returns the rows reached. */
    async function walk(key: string) {
      const reached: string[] = []
      for (let step = 0; step < 40; step++) {
        const before = await focused()
        await page.keyboard.press(key)
        const after = await focused()
        if (after === before) return reached
        expect(after).toBeDefined()
        await expectRingWhole(page, `${key} to ${after}`)
        reached.push(after!)
      }
      throw new Error(`${key} never stopped`)
    }
    await walk('ArrowUp')
    await expect(list.locator('[data-look]').first()).toBeFocused()
    expect(await list.evaluate((element) => element.scrollTop), 'at the top').toBe(0)
    expect((await walk('ArrowDown')).length, 'rows below').toBeGreaterThan(2)
    await expect(list.locator('[data-look]').last()).toBeFocused()
    expect((await walk('ArrowUp')).length, 'and back up').toBeGreaterThan(2)
  })

  // F4 ruling 12 on the phone: L opens the composer on the first row, Up and Down move through the rows and choose, Enter starts, Esc leaves.
  test('the keyboard puts a look on: L, the arrows and Enter', async ({ page }) => {
    await open(page, '/next/live')
    await page.keyboard.press('l')
    await expect(page).toHaveURL(/\/next\/live\/put$/)
    const rows = page.getByRole('group', { name: 'Looks' }).locator('[data-look]')
    await expect(rows.first()).toBeFocused()
    await page.keyboard.press('ArrowDown')
    await expect(rows.nth(1)).toBeFocused()
    await expect(page).toHaveURL(new RegExp(`look=${await rows.nth(1).getAttribute('data-look')}$`))
    await expect(rows.nth(1)).toHaveAttribute('aria-pressed', 'true')
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/\/next\/live$/)
    await expect(page.getByRole('status')).toHaveText(/^Started .+ on .+\.$/)

    await page.keyboard.press('l')
    await expect(rows.first()).toBeFocused()
    await page.keyboard.press('Escape')
    await expect(page).toHaveURL(/\/next\/live$/)
  })

  // Every control drawn shorter than --touch-min has a hit band that tall (CLAUDE.md, touch-target), once the boxes that clip it are taken
  // off: the chip rows pad by the band's reach, so the band is not cut at the row's edge.
  test('every control drawn shorter than --touch-min has a hit band that tall', async ({ page }) => {
    await open(page, still('/next/live/put?zone=living&look=embers'))
    const short = await shortControls(page.getByRole('region', { name: 'Put a look on' }))
    expect(
      short.map(({ control }) => control),
      'the sheet has controls under --touch-min, or this checks nothing',
    ).toEqual(expect.arrayContaining(['button Tempo', 'button Transition']))
    expect(short.filter(({ band, minimum }) => band < minimum - SLACK)).toEqual([])
  })
})
