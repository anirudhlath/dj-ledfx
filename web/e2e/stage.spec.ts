import { expect, test, type Page } from '@playwright/test'

// The stage in the browser, on the mock (the hero unless the path asks for another scenario): §8.1's
// room click and §7.6's frozen mode. The phone's stage has no labels or overlays (§8.10), and
// stage-view.test.tsx covers it, so this needs one project.
test.describe('the stage', () => {
  test.skip(({ isMobile }) => isMobile)

  /** Live's stage, once its canvas is on the page. */
  async function openStage(page: Page, path = '/next/live') {
    await page.goto(path)
    const stage = page.getByRole('region', { name: 'Home, live' })
    await expect(stage.locator('canvas')).toBeVisible()
    return stage
  }

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

  // Review focus 3, in the browser: the reconnecting scenario drops the link a second after it connects.
  test('freezes when the link drops: greyed, and no room opens the composer', async ({ page }) => {
    const stage = await openStage(page, '/next/live?scenario=reconnecting')
    await expect(stage.getByRole('navigation', { name: 'Rooms' })).toHaveCount(1)
    await expect(page.getByRole('status')).toHaveText('Reconnecting')
    await expect(stage.locator(':scope > div').first()).toHaveCSS('filter', /grayscale/)
    await expect(stage.getByRole('navigation', { name: 'Rooms' })).toHaveCount(0)
  })
})
