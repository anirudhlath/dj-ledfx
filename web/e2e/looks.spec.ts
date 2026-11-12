import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Locator, type Page } from '@playwright/test'
import { LIVE_SPEC } from '../src/design/live-numbers'
import { LIBRARY } from '../src/looks/looks-render'
import { KEEP_MOTIFS, open } from './helpers'

// The hero moment (spec §12.5): Wednesday 23 September, 19:14 in Dallas (timezoneId in the config).
const HERO_TIME = new Date('2026-09-23T19:14:00-05:00')

/** The tempo the mock's `inputs-down` scenario plays (Internal), which the beat thumb's rate is read against. */
const BPM = 118

/** The library on the mock's `library` scenario (Looks.png's stars, running pills and saved looks). */
const LIBRARY_PATH = '/next/looks?scenario=library'

/** open(), with the library drawn: its sections in, and the banner's tempo and frame rate settled, as shell.spec.ts's openStill(). */
async function openLibrary(page: Page, path: string) {
  await open(page, path)
  await expect(page.getByRole('heading', { level: 2, name: 'Firmware' })).toBeVisible()
  await expect(page.getByRole('banner').getByRole('group', { name: 'Tempo' })).toBeVisible()
  await expect(page.getByRole('banner').getByText('60 fps')).toBeVisible({ timeout: 10_000 })
}

/** axe's findings for the page as it stands, one line per rule. */
async function axeViolations(page: Page): Promise<string[]> {
  const { violations } = await new AxeBuilder({ page }).analyze()
  return violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)
}

/** The library's card for a look, by the id it carries. */
const cardOf = (page: Page, lookId: string): Locator => page.locator(`article[data-look="${lookId}"]`)

/** Every card's width by its look's id, to a tenth of a pixel: what a column that a long name widened would change. */
const cardWidths = (page: Page): Promise<Record<string, number>> =>
  page.locator('article[data-look]').evaluateAll((cards) => Object.fromEntries(cards.map((card) => [card.getAttribute('data-look')!, Math.round(card.getBoundingClientRect().width * 10) / 10])))

/** A card's thumb: the box the pill, the scrim and the motif are drawn in. */
const thumbOf = (card: Locator): Locator => card.locator('[data-thumb]')

/**
 * Puts the pointer at the thumb's top-left, clear of Put on… and Edit. The card's stretched name link covers the thumb (it is what a tap there
 * reaches), so Playwright's hit-test refuses the thumb: `force` moves the real pointer there anyway, and the link under it is inside the card's group.
 */
const hoverThumb = (thumb: Locator) => thumb.hover({ position: { x: 24, y: 24 }, force: true })

/** What a motif's animations say: when each has got to, and whether each is paused, with the page's clock beside them. */
function readMotion(svg: Locator) {
  return svg.evaluate((element) => {
    const animations = element.getAnimations({ subtree: true })
    return { at: performance.now(), times: animations.map((animation) => Number(animation.currentTime)), states: animations.map((animation) => animation.playState) }
  })
}

test.describe('Looks', () => {
  // Done when (spec §13.1 M5): the library matches Looks.png, and its thumbs follow the beat clock.
  test('matches Looks.png, with its hovered card', async ({ page }, info) => {
    test.skip(info.project.name !== 'desktop')
    await page.clock.setFixedTime(HERO_TIME)
    await openLibrary(page, `${LIBRARY_PATH}&still`)
    // The viewport grows to the page's whole height, as Looks.png draws it.
    await page.setViewportSize({
      width: 1440,
      height: await page.evaluate(() => document.documentElement.scrollHeight + (document.querySelector('main')!.scrollHeight - document.querySelector('main')!.clientHeight)),
    })
    // The pointer goes to the thumb's top, clear of Put on… and Edit, which the render draws at rest.
    await hoverThumb(thumbOf(cardOf(page, LIBRARY.hovered)))
    await expect(page).toHaveScreenshot('library.png', KEEP_MOTIFS)
  })

  // §5.4 "Beat-synced motion must follow the real beat clock, never a CSS timer", in Chromium and with no ?still: Internal at 118 BPM.
  test('moves a beat thumb at the live tempo, with its CSS paused', async ({ page }, info) => {
    test.skip(info.project.name !== 'desktop')
    await open(page, '/next/looks?scenario=inputs-down')
    // The rate window below is built on this scenario's tempo, so a tempo that moved fails here, by name, and not as a rate that is merely off.
    await expect(page.getByRole('banner').getByRole('group', { name: 'Tempo' }), `inputs-down no longer plays Internal at ${BPM} BPM, which the rate below assumes`).toContainText(`${BPM}.0`)
    const svg = page.locator('svg.tb[data-beat]').first()
    // The first beat thumb sits at the viewport's bottom edge, and a thumb off screen rests: it must be on screen to be read.
    await svg.scrollIntoViewIfNeeded()
    await expect.poll(async () => (await readMotion(svg)).times.some((time) => time > 0), { message: 'the thumb was never seeked to the beat' }).toBe(true)
    const first = await readMotion(svg)
    await page.waitForTimeout(3000)
    const second = await readMotion(svg)
    expect(second.times.length, 'a beat motif with no animation checks nothing').toBeGreaterThan(0)
    expect(second.times).toHaveLength(first.times.length)
    // The CSS is paused (Looks.html's keyframes are a stand-in), and the beat clock moves the time: one beat of 118 BPM is
    // 60 000 / 118 ms, which the motif's one-beat keyframe at LIVE_SPEC.mockBpm (121.8) covers in 60 000 / 121.8, so 118 / 121.8 = 0.969 of the wall clock.
    const expected = BPM / LIVE_SPEC.mockBpm
    for (const [i, state] of second.states.entries()) {
      expect(state, `animation ${i}`).toBe('paused')
      const rate = (second.times[i] - first.times[i]) / (second.at - first.at)
      expect(rate, `animation ${i}`).toBeGreaterThan(expected - 0.025)
      expect(rate, `animation ${i}`).toBeLessThan(expected + 0.025)
    }
  })

  // F5 decision 6: a held beat holds every thumb, the CSS rule's `data-paused` and the animations' own time both.
  test('holds every thumb under ?still', async ({ page }) => {
    await open(page, `${LIBRARY_PATH}&still`)
    await expect(page.getByRole('heading', { level: 2, name: 'Firmware' })).toBeVisible()
    const thumbs = page.locator('svg.tb')
    expect(await thumbs.count(), 'the library draws motifs').toBeGreaterThan(20)
    const read = () => thumbs.evaluateAll((svgs) => svgs.map((svg) => ({ paused: svg.hasAttribute('data-paused'), times: svg.getAnimations({ subtree: true }).map((animation) => `${animation.playState} ${animation.currentTime}`) })))
    const before = await read()
    await page.waitForTimeout(1000)
    const after = await read()
    expect(before.every((thumb) => thumb.paused), 'every motif carries data-paused').toBe(true)
    expect(before.flatMap((thumb) => thumb.times).length, 'the motifs have animations, or this checks nothing').toBeGreaterThan(0)
    expect(before.flatMap((thumb) => thumb.times).every((time) => time.startsWith('paused')), 'every animation is paused').toBe(true)
    expect(after).toEqual(before)
  })

  // §5.4 "Pause thumbnails that are off screen" (F5 plan, Review Focus 5). The attribute alone proves nothing, since tokens.css's reduced-motion
  // rule is the other guard: the animations' own time is read too. A firmware motif is ambient, so it runs its own CSS loop while it's on screen.
  test('runs a thumb on screen and rests it off screen', async ({ page }, info) => {
    test.skip(info.project.name !== 'desktop')
    await open(page, LIBRARY_PATH)
    const section = page.locator('section', { has: page.getByRole('heading', { level: 2, name: 'Firmware' }) })
    const svg = section.locator('svg.tb').first()
    const main = page.locator('main')

    const rests = async () => {
      await expect(svg).toHaveAttribute('data-paused', '')
      const first = await readMotion(svg)
      await page.waitForTimeout(500)
      const second = await readMotion(svg)
      expect(second.times.length, 'the motif has animations, or this checks nothing').toBeGreaterThan(0)
      expect(second.times).toEqual(first.times)
      expect(second.states.every((state) => state === 'paused')).toBe(true)
    }
    await rests()

    await svg.scrollIntoViewIfNeeded()
    await expect(svg).not.toHaveAttribute('data-paused')
    const first = await readMotion(svg)
    await page.waitForTimeout(500)
    const second = await readMotion(svg)
    expect(second.states.some((state) => state === 'running')).toBe(true)
    expect(second.times.some((time, i) => time > first.times[i])).toBe(true)

    await main.evaluate((element) => element.scrollTo(0, 0))
    await rests()
  })

  test('has no axe violations, hovered or not', async ({ page, isMobile }) => {
    await open(page, `${LIBRARY_PATH}&still`)
    await expect(page.getByRole('heading', { level: 2, name: 'Firmware' })).toBeVisible()
    expect(await axeViolations(page)).toEqual([])
    // A touch screen has no hover (Tailwind gates group-hover on it), so the scrim is the desktop's.
    if (isMobile) return
    await hoverThumb(thumbOf(cardOf(page, LIBRARY.hovered)))
    await expect.poll(() => cardOf(page, LIBRARY.hovered).getByRole('link', { name: 'Put on…' }).locator('..').evaluate((scrim) => getComputedStyle(scrim).opacity)).toBe('1')
    expect(await axeViolations(page)).toEqual([])
  })

  // The card's overlays, in Chromium (look-card.test.tsx has no layout): LookCard's own layering is what these pin.
  test.describe('a library card', () => {
    test.skip(({ isMobile }) => isMobile)

    test.beforeEach(async ({ page }) => {
      await open(page, `${LIBRARY_PATH}&still`)
      await expect(page.getByRole('heading', { level: 2, name: 'Firmware' })).toBeVisible()
    })

    /** The scrim over a card's thumb, the box that holds Put on… and Edit. */
    const scrimOf = (card: Locator): Locator => card.getByRole('link', { name: 'Put on…' }).locator('..')

    /** Whether the element at the centre of `locator` is `locator` itself or something in it, and what else it is if not (a link's text, or a tag). */
    const hitAt = (locator: Locator) =>
      locator.evaluate((element) => {
        const box = element.getBoundingClientRect()
        const hit = document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2)
        return { own: hit !== null && element.contains(hit), other: hit?.closest('a')?.getAttribute('href') ?? hit?.tagName ?? null }
      })

    test('shows its scrim and white border on hover, and Put on… and Edit take a pointer only under it', async ({ page }) => {
      const card = cardOf(page, LIBRARY.hovered)
      const thumb = thumbOf(card)
      const scrim = scrimOf(card)
      const put = card.getByRole('link', { name: 'Put on…' })
      const edit = card.getByRole('link', { name: 'Edit', exact: true })
      const opacity = () => scrim.evaluate((element) => getComputedStyle(element).opacity)
      const border = () => thumb.evaluate((element) => getComputedStyle(element).borderTopColor)
      const textColour = await card.getByRole('heading').evaluate((heading) => getComputedStyle(heading).color)

      // At rest: no scrim, the line's border, and a tap on the thumb goes to the name's link (the card's editor link).
      await page.mouse.move(5, 5)
      expect(await opacity()).toBe('0')
      expect(await border()).not.toBe(textColour)
      for (const button of [put, edit]) expect(await hitAt(button)).toEqual({ own: false, other: `/next/looks/${LIBRARY.hovered}` })

      // Hovered: the scrim at full strength, the border the text's colour (white), a gradient from the bottom, and each button hit.
      await hoverThumb(thumb)
      await expect.poll(opacity).toBe('1')
      expect(await border()).toBe(textColour)
      expect(await scrim.evaluate((element) => getComputedStyle(element).backgroundImage)).toContain('linear-gradient')
      for (const button of [put, edit]) expect(await hitAt(button)).toMatchObject({ own: true })
      // They sit inside the thumb, below the middle, side by side.
      const [thumbBox, putBox, editBox] = await Promise.all([thumb.boundingBox(), put.boundingBox(), edit.boundingBox()])
      expect(thumbBox && putBox && editBox).toBeTruthy()
      for (const box of [putBox!, editBox!]) {
        expect(box.x).toBeGreaterThanOrEqual(thumbBox!.x)
        expect(box.x + box.width).toBeLessThanOrEqual(thumbBox!.x + thumbBox!.width)
        expect(box.y).toBeGreaterThan(thumbBox!.y + thumbBox!.height / 2)
        expect(box.y + box.height).toBeLessThanOrEqual(thumbBox!.y + thumbBox!.height)
      }
      expect(editBox!.x).toBeGreaterThan(putBox!.x + putBox!.width)

      // Away again: the scrim goes, and the buttons stop taking a pointer.
      await page.mouse.move(5, 5)
      await expect.poll(opacity).toBe('0')
      for (const button of [put, edit]) expect(await hitAt(button)).toMatchObject({ own: false })
    })

    test('keeps a starred card’s star lit, hovered or not, and the star out from under the scrim', async ({ page }) => {
      // The render's hovered card is starred, so it's the one to look at hovered.
      const hovered = cardOf(page, LIBRARY.hovered)
      expect(LIBRARY.starred).toContain(LIBRARY.hovered)
      const star = (card: Locator) => card.getByRole('button', { name: /^(Unstar|Star) / })
      const look = (button: Locator) =>
        button.evaluate((element) => {
          const icon = element.querySelector('svg')!
          return { colour: getComputedStyle(element).color, fill: getComputedStyle(icon).fill, pressed: element.getAttribute('aria-pressed') }
        })
      const textColour = await hovered.getByRole('heading').evaluate((heading) => getComputedStyle(heading).color)

      const lit = { colour: textColour, pressed: 'true' }
      await page.mouse.move(5, 5)
      expect(await look(star(hovered))).toMatchObject(lit)
      expect((await look(star(hovered))).fill).not.toBe('none')
      await hoverThumb(thumbOf(hovered))
      await expect.poll(() => scrimOf(hovered).evaluate((element) => getComputedStyle(element).opacity)).toBe('1')
      expect(await look(star(hovered))).toMatchObject(lit)
      // The pointer on the star itself: still lit, and the star is what a tap there reaches, not the stretched link or the scrim.
      await star(hovered).hover()
      expect(await look(star(hovered))).toMatchObject(lit)
      expect(await hitAt(star(hovered))).toMatchObject({ own: true })

      // An unstarred card's star is another colour, and unfilled: the lit one means something.
      const plain = page.locator('article[data-look]', { has: page.getByRole('button', { name: /^Star / }) }).first()
      await page.mouse.move(5, 5)
      const unlit = await look(star(plain))
      expect(unlit.pressed).toBe('false')
      expect(unlit.colour).not.toBe(textColour)
      expect(unlit.fill).toBe('none')
    })
  })

  // §6.4: a name the owner typed can be any length (a saved look's, a zone's). The mock serves the library with two of them made long, and a pill
  // must keep to its thumb, cut short with an ellipsis, with its dot still its size; no card and not the page widen. Both projects run it:
  // the phone's cards are the narrower, so a pill is cut there first.
  test("keeps a long look name's pill, and a long zone's, inside the thumb", async ({ page }) => {
    const [runningLook, zoneName] = Object.entries(LIBRARY.running)[0]
    const parent = LIBRARY.mine[0].from
    // The library as the mock serves it, to measure the cards against once two names are long.
    await open(page, `${LIBRARY_PATH}&still`)
    await expect(page.getByRole('heading', { level: 2, name: 'Firmware' })).toBeVisible()
    const before = await cardWidths(page)
    expect(Object.keys(before).length, 'the library draws its cards').toBeGreaterThan(20)
    await page.addInitScript(
      ({ parent, zoneName, long }) => {
        // The mock plays in this page (MSW's worker), so a Playwright route can't reach it: the page's own fetch is wrapped instead.
        const original = window.fetch
        window.fetch = async (input, init) => {
          const response = await original(input, init)
          const url = new URL(input instanceof Request ? input.url : String(input), location.href)
          const rename = url.pathname.endsWith('/api/looks')
            ? (items: { id: string; name: string }[]) => items.map((item) => (item.id === parent ? { ...item, name: `${long} ${item.name}` } : item))
            : url.pathname.endsWith('/api/zones')
              ? (items: { id: string; name: string }[]) => items.map((item) => (item.name === zoneName ? { ...item, name: `${long} ${item.name}` } : item))
              : null
          if (rename === null || !response.ok) return response
          return new Response(JSON.stringify(rename(await response.json())), { status: response.status, statusText: response.statusText, headers: response.headers })
        }
      },
      { parent, zoneName, long: 'A name the owner typed that runs on and on' },
    )
    await open(page, `${LIBRARY_PATH}&still`)
    await expect(page.getByRole('heading', { level: 2, name: 'Firmware' })).toBeVisible()

    const pills = [
      { name: 'the From pill', text: page.getByText(/^From A name the owner typed/) },
      { name: 'the running pill', text: cardOf(page, runningLook).locator('span.truncate', { hasText: /^A name the owner typed/ }) },
    ]
    // A short pill's dot, for its size.
    const shortDot = await page.locator('article[data-look]').evaluateAll((cards) => {
      const dot = cards.map((card) => card.querySelector('span.rounded-full')).find((each): each is Element => each !== null && each.nextElementSibling?.textContent?.length === 'Whole home'.length)
      return dot?.getBoundingClientRect().width ?? 0
    })
    expect(shortDot, 'a pill with a dot to measure').toBeGreaterThan(0)

    for (const { name, text } of pills) {
      await expect(text, name).toHaveCount(1)
      const fit = await text.evaluate((span) => {
        const pill = span.parentElement!
        const card = pill.closest('article')!
        const thumb = card.querySelector('[data-thumb]')!.getBoundingClientRect()
        const box = pill.getBoundingClientRect()
        // The pill is a fixed-height row, so its own box says nothing of a label that wrapped: the label's text is counted by its line boxes instead.
        const range = document.createRange()
        range.selectNodeContents(span)
        return {
          inside: box.left >= thumb.left && box.right <= thumb.right && box.top >= thumb.top && box.bottom <= thumb.bottom,
          cut: span.scrollWidth > span.clientWidth && getComputedStyle(span).textOverflow === 'ellipsis',
          lines: new Set([...range.getClientRects()].map((rect) => Math.round(rect.top))).size,
          hidden: span.scrollHeight - span.clientHeight,
          dot: pill.querySelector('span.rounded-full')?.getBoundingClientRect().width ?? null,
          pillRight: box.right,
          cardRight: card.getBoundingClientRect().right,
        }
      })
      expect(fit.inside, `${name} is inside its thumb`).toBe(true)
      expect(fit.cut, `${name} is cut short with an ellipsis`).toBe(true)
      expect(fit.lines, `${name}'s label keeps to one line`).toBe(1)
      expect(fit.hidden, `${name}'s label has no second line hidden below it`).toBeLessThanOrEqual(0)
      expect(fit.pillRight, `${name} stays inside its card's right edge`).toBeLessThanOrEqual(fit.cardRight)
      if (fit.dot !== null) expect(fit.dot, `${name}'s dot keeps its size`).toBe(shortDot)
    }
    // The page doesn't scroll sideways for any of it, and every card is the width it was with the names as the mock serves them.
    expect(await page.locator('main').evaluate((main) => main.scrollWidth - main.clientWidth)).toBeLessThanOrEqual(0)
    expect(await cardWidths(page), 'no card is wider or narrower than it was').toEqual(before)
  })
})
