import { expect, test, type Page } from '@playwright/test'
import { SPEC } from '../src/stage/design-numbers'
import { stageCanvas } from './helpers'

// §14 Performance on Live, against SPEC.quality: the stage's frame rate with every LED streaming
// (the firmware scenario streams all of the home's LEDs at the mock's full rate: mock-server.test.ts),
// and how much of the time the main thread is busy. A render is a burst of WebGL draw calls; the gaps
// between renders give the frame rate. The phone is a desktop GPU with the CPU slowed down.

/** How long the page settles, and how long it's measured. */
const SETTLE_MS = 3000
const WINDOW_MS = 5000
/** Draw calls closer together than this are one render. */
const BURST_MS = 4
/** Chrome DevTools' "mid-tier mobile" CPU. */
const PHONE_CPU_SLOWDOWN = 4

/** In the page, before its scripts: every WebGL draw call's time, in `window.stageDraws`. */
function recordDraws() {
  const draws: number[] = []
  Object.assign(window, { stageDraws: draws })
  const gl = WebGL2RenderingContext.prototype as unknown as Record<string, (...args: unknown[]) => unknown>
  for (const name of ['drawArrays', 'drawElements', 'drawArraysInstanced', 'drawElementsInstanced']) {
    const draw = gl[name]
    gl[name] = function (this: unknown, ...args: unknown[]) {
      draws.push(performance.now())
      return draw.apply(this, args)
    }
  }
}

interface Measured {
  renderer: string
  /** Each render's time, in the measured window. */
  renders: number[]
  /** The main thread's share of the window spent on tasks. */
  busy: number
}

async function measure(page: Page, path: string, cpuSlowdown: number): Promise<Measured> {
  await page.addInitScript(recordDraws)
  const cdp = await page.context().newCDPSession(page)
  await cdp.send('Performance.enable')
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: cpuSlowdown })
  // Not open(): the phone's header shows no attention button while nothing needs attention, as in the
  // firmware scenario, so this waits for the stage's canvas alone.
  await page.goto(path)
  await expect(stageCanvas(page)).toBeVisible()
  await page.waitForTimeout(SETTLE_MS)

  const metrics = async () => new Map((await cdp.send('Performance.getMetrics')).metrics.map((m) => [m.name, m.value]))
  const before = await metrics()
  const start = await page.evaluate(() => performance.now())
  await page.waitForTimeout(WINDOW_MS)
  const after = await metrics()
  const { draws, renderer } = await page.evaluate(() => {
    const gl = document.createElement('canvas').getContext('webgl2')
    const info = gl?.getExtension('WEBGL_debug_renderer_info')
    return {
      draws: (window as unknown as { stageDraws: number[] }).stageDraws,
      renderer: gl && info ? String(gl.getParameter(info.UNMASKED_RENDERER_WEBGL)) : 'none',
    }
  })

  const renders: number[] = []
  for (const at of draws.filter((t) => t >= start && t < start + WINDOW_MS)) {
    if (renders.length === 0 || at - renders[renders.length - 1] > BURST_MS) renders.push(at)
  }
  const busy = (after.get('TaskDuration')! - before.get('TaskDuration')!) / (after.get('Timestamp')! - before.get('Timestamp')!)
  return { renderer, renders, busy }
}

/** The gap between renders that 95% of gaps are shorter than, in ms. */
function p95Gap(renders: readonly number[]): number {
  const gaps = renders.slice(1).map((at, i) => at - renders[i]).sort((a, b) => a - b)
  return gaps[Math.floor(0.95 * (gaps.length - 1))]
}

test('the stage keeps its frame rate with every LED streaming, and the main thread stays idle', async ({ page, isMobile }) => {
  const { renderer, renders, busy } = await measure(page, '/next/live?scenario=firmware', isMobile ? PHONE_CPU_SLOWDOWN : 1)
  console.log(JSON.stringify({ project: isMobile ? 'phone' : 'desktop', renderer, fps: renders.length / (WINDOW_MS / 1000), p95GapMs: p95Gap(renders), busy }))
  expect(renderer, 'measured on the GPU, not the software renderer').not.toMatch(/SwiftShader|llvmpipe|none/i)
  if (isMobile) {
    // The phone draws at most SPEC.phoneFps (§7.5): every one of those, give or take the window's ends.
    expect(renders.length).toBeGreaterThanOrEqual((SPEC.quality.phoneFps * WINDOW_MS) / 1000 - 1)
  } else {
    expect(1000 / p95Gap(renders)).toBeGreaterThanOrEqual(SPEC.quality.desktopFps)
  }
  expect(busy).toBeLessThanOrEqual(1 - SPEC.quality.idle)
})
