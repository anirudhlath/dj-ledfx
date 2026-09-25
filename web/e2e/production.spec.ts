import { expect, test } from '@playwright/test'

// D4: the production bundle, as FastAPI serves it at /next, with no backend behind it and no
// mocks in it (the second web server in playwright.config.ts). One project is enough.
const PRODUCTION = 'http://localhost:4175'

test.describe('the production bundle', () => {
  test.skip(({ isMobile }) => isMobile)

  test('draws the shell and says Reconnecting when no server answers', async ({ page }) => {
    await page.goto(`${PRODUCTION}/next/live`)
    await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible()
    await expect(page.getByRole('heading', { level: 1, name: 'Live' })).toBeVisible()
    await expect(page.getByRole('status')).toHaveText('Reconnecting')
    await expect(page.getByRole('banner').getByText('· try 1')).toBeVisible()
    // Nothing claims what only a server could say.
    await expect(page.getByRole('banner').getByRole('button', { name: /All good|attention/ })).toHaveCount(0)
    // MSW never came: no service worker.
    expect(await page.evaluate(async () => (await navigator.serviceWorker.getRegistrations()).length)).toBe(0)
  })
})
