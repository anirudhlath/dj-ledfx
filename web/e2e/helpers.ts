// What the e2e specs share: opening a page on the mock, and Live's stage.
import { expect, type Locator, type Page } from '@playwright/test'

/**
 * Opens a page and waits for the chrome's first data from the mock (the hero, unless the path asks
 * for another scenario): the attention button, whatever it says.
 */
export async function open(page: Page, path: string): Promise<void> {
  await page.goto(path)
  // The mock build renders once MSW's worker is up (app/boot.tsx), so the chrome comes first, then its fonts.
  await expect(page.getByRole('banner').getByRole('button', { name: /needs attention$|^All good$/ })).toBeVisible()
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
