import { expect, test, type Page } from '@playwright/test'
import { fxPictured, open, openStage, stageCanvas } from './helpers'

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

  // jsdom has no WebGL, so the rings' and planes' shaders compile and draw only here. Each look is previewed under ?still on a
  // room with lights, in a scenario where nothing else runs, so the preview's picture is all the stage draws in space: with
  // reduced motion it draws none (§5.4, F10 ruling 4), so a canvas that differs between the two has drawn the picture. A look
  // that draws nothing in space is the control: reduced motion alone changes nothing on the canvas. three logs a shader that
  // fails to compile or link to the console and draws nothing, so the console is checked first. Speaker waves sends a sphere
  // alone, so a sphere that draws nothing fails it, where Shockwave's plane would hide it.
  for (const [look, kinds] of [
    ['shockwave', 'a sphere ring and a plane with a ray'],
    ['speakers', 'a sphere ring alone'],
    ['ripples', 'circle rings'],
    ['scanner', 'a level plane'],
    ['lava', 'nothing (the control)'],
  ] as const) {
    test(`draws ${kinds} in space for ${look}, and its shaders compile`, async ({ page }) => {
      const messages: string[] = []
      page.on('console', (message) => {
        if (message.type() === 'error' || message.type() === 'warning') messages.push(message.text())
      })
      page.on('pageerror', (error) => messages.push(error.message))
      await page.emulateMedia({ reducedMotion: 'no-preference' })
      await open(page, `/next/live/put?scenario=nothing-running&zone=living&look=${look}&still`)
      const canvas = stageCanvas(page)
      await expect(canvas).toBeVisible()
      await expect(page.getByText(/^Preview on screen/)).toBeVisible()
      await fxPictured(page, { preview: look !== 'lava' })
      const shot = () => canvas.screenshot({ animations: 'disabled' })
      // The canvas at rest: unchanged over a second, past the preview's first frames and reduced motion's one draw a second (§5.4).
      const steady = async () => {
        let last = await shot()
        await expect
          .poll(
            async () => {
              await page.waitForTimeout(1200)
              const now = await shot()
              const moved = await changed(page, last, now)
              last = now
              return moved
            },
            { timeout: 15_000 },
          )
          .toBe(0)
        return last
      }
      const drawn = await steady()
      await page.emulateMedia({ reducedMotion: 'reduce' })
      const gone = await changed(page, drawn, await steady())
      // Two warnings every SwiftShader run gives, which say nothing about the stage's shaders. Checked before the canvas, so a
      // shader that fails says why.
      const benign = /KHR_parallel_shader_compile extension not supported|GPU stall due to ReadPixels/
      expect(messages.filter((text) => /WebGLProgram|Shader Error|WebGL/.test(text) && !benign.test(text))).toEqual([])
      console.log(`${look}: ${gone} pixels differ with the effects in space gone`)
      if (look === 'lava') expect(gone).toBe(0)
      else expect(gone).toBeGreaterThan(MANY_PIXELS)
    })
  }

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

/** More pixels than a stray glint: a ring or a plane drawn faintly across a room covers thousands. */
const MANY_PIXELS = 200

/**
 * How many pixels of two PNG screenshots of one size differ by more than `by` levels in a channel, counted in the page. The
 * software renderer can draw the same picture a level apart from one draw to the next, so an exact comparison would see a change;
 * a ring drawn faintly at the glass's alpha is only some levels above the floor, so the margin is no wider than that noise needs.
 */
function changed(page: Page, a: Buffer, b: Buffer, by = 2): Promise<number> {
  return page.evaluate(
    async ([a, b, by]) => {
      const pixels = async (base64: string) => {
        const bytes = Uint8Array.from(atob(base64), (char) => char.charCodeAt(0))
        const image = await createImageBitmap(new Blob([bytes], { type: 'image/png' }))
        const context = new OffscreenCanvas(image.width, image.height).getContext('2d')!
        context.drawImage(image, 0, 0)
        return context.getImageData(0, 0, image.width, image.height).data
      }
      const [x, y] = await Promise.all([pixels(a), pixels(b)])
      let count = 0
      for (let i = 0; i < x.length; i += 4) {
        if (Math.abs(x[i] - y[i]) > by || Math.abs(x[i + 1] - y[i + 1]) > by || Math.abs(x[i + 2] - y[i + 2]) > by) count++
      }
      return count
    },
    [a.toString('base64'), b.toString('base64'), by] as const,
  )
}
