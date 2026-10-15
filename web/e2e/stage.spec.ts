import { expect, test } from '@playwright/test'
import { open, openStage, stageCanvas } from './helpers'

// The stage in the browser, on the mock (the hero unless the path asks for another scenario): §8.1's
// room click, §7.6's frozen mode and §7.4's effects in space. The phone's stage has no labels or overlays (§8.10), and
// stage-view.test.tsx covers it, so this needs one project.
test.describe('the stage', () => {
  test.skip(({ isMobile }) => isMobile)

  // §8.1: "Click a room → /live/put?zone=<room>". The rooms' links (the stage's keyboard way in)
  // name a room with lights and where it goes; a click on that room's label on the floor goes there too.
  test('a click on a room with lights opens the composer for it', async ({ page }) => {
    const stage = await openStage(page)
    const link = stage.getByRole('navigation', { name: 'Rooms' }).getByRole('link').first()
    const room = (await link.textContent())!.replace(/^Put a look on /, '')
    const href = (await link.getAttribute('href'))!
    // The SVG layer lets the pointer through to the picture, so the click goes where the label is drawn.
    const label = (await stage.getByText(room, { exact: true }).boundingBox())!
    await page.mouse.click(label.x + label.width / 2, label.y + label.height / 2)
    await page.waitForURL((url) => `${url.pathname}${url.search}` === href)
  })

  // §7.4: "This is the "Effects in space" toggle (default on)". Under ?still the mock holds its frames and
  // sends one picture of the effects in space, so the canvas is the same draw after draw: the switch takes
  // the hero's fireflies and comets off it and puts them back, and Live remembers it off.
  test('draws the effects in space, and the switch takes them off and back, remembered', async ({ page }) => {
    const stage = await openStage(page, '/next/live?still')
    const effects = stage.getByRole('switch', { name: 'Effects in space' })
    await expect(effects).toHaveAttribute('aria-checked', 'true')
    const canvas = stageCanvas(page)
    const shot = () => canvas.screenshot()
    // Drawn with the picture: it changes once more after the first draw, as the picture lands, then holds.
    await expect.poll(async () => (await shot()).equals(await shot()), { timeout: 5000 }).toBe(true)
    await effects.click()
    await expect(effects).toHaveAttribute('aria-checked', 'false')
    await expect.poll(async () => (await shot()).equals(await shot())).toBe(true)
    const off = await shot()
    await effects.click()
    await expect.poll(async () => (await shot()).equals(off), { timeout: 5000 }).toBe(false)
    // Off again, and after a reload still off: putting them on changes the picture.
    await effects.click()
    await page.reload()
    const reloaded = page.getByRole('switch', { name: 'Effects in space' })
    await expect(reloaded).toHaveAttribute('aria-checked', 'false')
    await expect(canvas).toBeVisible()
    await expect.poll(async () => (await shot()).equals(await shot())).toBe(true)
    const stillOff = await shot()
    await reloaded.click()
    await expect.poll(async () => (await shot()).equals(stillOff), { timeout: 5000 }).toBe(false)
  })

  // Review focus 3, in the browser: the reconnecting scenario drops the link a second after it connects. The
  // rooms' links come with the stage, before its canvas, whose shaders can take most of that second to compile.
  test('freezes when the link drops: greyed, and no room opens the composer', async ({ page }) => {
    await open(page, '/next/live?scenario=reconnecting')
    const stage = page.getByRole('region', { name: 'Home, live' })
    await expect(stage.getByRole('navigation', { name: 'Rooms' })).toHaveCount(1)
    await expect(stageCanvas(page)).toBeVisible()
    await expect(page.getByRole('status')).toHaveText('Reconnecting')
    await expect(stage.locator(':scope > div').first()).toHaveCSS('filter', /grayscale/)
    await expect(stage.getByRole('navigation', { name: 'Rooms' })).toHaveCount(0)
  })
})
