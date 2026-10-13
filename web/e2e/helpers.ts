// What the e2e specs share: opening a page on the mock, Live's stage, and a notched screen.
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
