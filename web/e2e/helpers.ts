// What the e2e specs share: opening a page on the mock, Live's stage, a notched screen, and what the layout checks measure with.
import { expect, type Locator, type Page } from '@playwright/test'

/**
 * Opens a page and waits for the chrome's first data from the mock (the hero, unless the path asks
 * for another scenario): the attention button, whatever it says, or on the phone's Put a look on, a
 * focused task with no header (Phone-PutLookOn), the looks it offers; or `ready` where there's none
 * of those to wait for (the phone's header hides the button while nothing needs attention).
 */
export async function open(page: Page, path: string, ready?: Locator): Promise<void> {
  await page.goto(path)
  // The mock build renders once MSW's worker is up (app/boot.tsx), so the chrome comes first, then its fonts.
  const attention = page.getByRole('banner').getByRole('button', { name: /needs? attention$|^All good$/ })
  // The phone's composer is a region of that name; the desktop's is an aside with a Looks group of its own, which must not stand in for the button.
  const sheet = page.getByRole('region', { name: 'Put a look on' }).getByRole('group', { name: 'Looks' })
  await expect(ready ?? attention.or(sheet).first()).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
}

/** Live's stage: its section, by the name a screen reader reads. */
function stageOf(page: Page): Locator {
  return page.getByRole('region', { name: 'Home, live' })
}

/** The stage's canvas, which shows once three has compiled the stage's shaders. */
export function stageCanvas(page: Page): Locator {
  return stageOf(page).locator('canvas')
}

/**
 * The stage has drawn the mock's pictures of the effects in space, so a screenshot of a stage that draws them can't
 * settle before the picture lands. The mock counts the pictures it sends (src/api/mocks/browser.ts marks the page), and
 * the stage's canvas names the fx store's version it last drew (scene/fx-layer.tsx), which moves at least once a
 * picture stored: this waits for the first, then for the second to catch up with it. A stage frozen before it asked
 * for a picture never gets one, and a stage that draws none never marks its canvas.
 */
export async function fxPictured(page: Page): Promise<void> {
  const sent = page.locator('html[data-mock-fx]')
  await expect(sent).toHaveCount(1)
  await expect
    .poll(async () => {
      const [count, drawn] = [await sent.getAttribute('data-mock-fx'), await stageCanvas(page).getAttribute('data-fx-drawn')]
      return drawn !== null && Number(drawn) >= Number(count)
    })
    .toBe(true)
}

/** open(), then Live's stage once its canvas shows. */
export async function openStage(page: Page, path = '/next/live'): Promise<Locator> {
  await open(page, path)
  await expect(stageCanvas(page)).toBeVisible()
  return stageOf(page)
}

export type Insets = { top: number; right: number; bottom: number; left: number }

/** A notched screen: Chromium's safe-area override stands in for the phone's (viewport-fit=cover). */
export async function notch(page: Page, insets: Insets): Promise<void> {
  const cdp = await page.context().newCDPSession(page)
  await cdp.send('Emulation.setSafeAreaInsetsOverride', { insets })
}

/** Layout's rounding: a fraction of a pixel is neither a cut ring, nor a scroll, nor a hit band short of --touch-min. */
export const SLACK = 0.5

/** How far <main> can scroll (what its content has beyond its box), and the offset it is scrolled to: a page that fits it has neither. */
export function mainScroll(page: Page) {
  return page.locator('main').evaluate((main) => ({ beyond: main.scrollHeight - main.clientHeight, at: main.scrollTop }))
}

/** Waits until nothing on the page scrolls any more: every element's offsets are the same for five frames running. */
export function settled(page: Page): Promise<void> {
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

/**
 * Whether the focused element's ring is whole: how far it reaches past the viewport and past the scrollport of every ancestor that clips it
 * (a row that scrolls on its own, and the sheet or the panel around it), side by side. A ring reaches its outline's width and offset beyond
 * the element (tokens.css); 0 or less on every side of every clipper is a whole ring. The page must have settled.
 */
export async function expectRingWhole(page: Page, what: string) {
  await settled(page)
  const { ring, worst } = await page.evaluate(() => {
    const element = document.activeElement
    if (!(element instanceof HTMLElement)) throw new Error('nothing has the focus')
    const style = getComputedStyle(element)
    if (style.outlineStyle === 'none') throw new Error(`${element.tagName} draws no focus ring`)
    const reach = parseFloat(style.outlineWidth) + parseFloat(style.outlineOffset)
    const own = element.getBoundingClientRect()
    const past = (port: { left: number; top: number; right: number; bottom: number }) => ({
      left: port.left - (own.left - reach),
      right: own.right + reach - port.right,
      top: port.top - (own.top - reach),
      bottom: own.bottom + reach - port.bottom,
    })
    const bounds: { by: string; past: ReturnType<typeof past> }[] = [{ by: 'the viewport', past: past({ left: 0, top: 0, right: innerWidth, bottom: innerHeight }) }]
    for (let clip = element.parentElement; clip && clip !== document.documentElement; clip = clip.parentElement) {
      const { overflowX, overflowY } = getComputedStyle(clip)
      if (overflowX === 'visible' && overflowY === 'visible') continue
      // The scrollport: the box inside the clipper's border, and inside its scrollbar.
      const edge = clip.getBoundingClientRect()
      const left = edge.left + clip.clientLeft
      const top = edge.top + clip.clientTop
      bounds.push({ by: `${clip.tagName.toLowerCase()}[${clip.getAttribute('aria-label') ?? clip.getAttribute('role') ?? clip.className.slice(0, 24)}]`, past: past({ left, top, right: left + clip.clientWidth, bottom: top + clip.clientHeight }) })
    }
    const worst = bounds
      .map(({ by, past: sides }) => ({ by, sides, most: Math.max(...Object.values(sides)) }))
      .reduce((a, b) => (b.most > a.most ? b : a))
    return { ring: reach, worst }
  })
  expect(worst.most, `${what}: its ${ring} px ring reaches past ${worst.by} by ${JSON.stringify(worst.sides)}`).toBeLessThanOrEqual(SLACK)
}

/**
 * Every absolutely positioned element in <main> that a clip cuts off from its containing block, as a line each: an element's containing block
 * is its nearest positioned ancestor (a transform or the like makes one too), and a clipping ancestor between the two leaves it neither
 * clipped nor scrolled with that ancestor, so a hidden label (sr-only) there stretches <main>'s scroll area. `examined` counts the elements looked at.
 */
export function absoluteEscapes(page: Page) {
  return page.locator('main').evaluate((main) => {
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
}

/**
 * Presses `key` until the focus stops moving, with every look it reaches (`[data-look]`) rung whole; returns the ids reached. For a list
 * or grid whose arrows move the focus.
 */
export async function walkLooks(page: Page, key: string): Promise<string[]> {
  const focused = () => page.evaluate(() => (document.activeElement as HTMLElement).dataset.look)
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
