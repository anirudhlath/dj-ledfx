import { expect, test } from '@playwright/test'

// Review focus 1 and §14 Resilience, in the browser: the reconnecting scenario drops the link a
// second after it connects, then refuses every retry. The phone header says the same in its pill
// (shell.test.tsx); this needs one project.
test.describe('the link', () => {
  test.skip(({ isMobile }) => isMobile)

  test('says Reconnecting within 2 s of a drop, and counts the retries', async ({ page }) => {
    await page.goto('/next/live?scenario=reconnecting')
    const banner = page.getByRole('banner')
    await expect(banner.getByRole('button', { name: '1 needs attention' })).toBeVisible()
    const connected = Date.now()

    await expect(page.getByRole('status')).toHaveText('Reconnecting')
    // The mock drops the link 1 s after it connects, and §14 allows 2 s from there.
    expect(Date.now() - connected).toBeLessThan(3000)
    await expect(banner.getByText('· try 1')).toBeVisible()
    // The retry 1 s later is refused, so the count moves on.
    await expect(banner.getByText('· try 2')).toBeVisible({ timeout: 5000 })
    // What the server said before it went stays on screen, and nothing claims All good.
    await expect(banner.getByRole('button', { name: '1 needs attention' })).toBeVisible()
  })
})
