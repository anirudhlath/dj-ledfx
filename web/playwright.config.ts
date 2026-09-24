import { defineConfig } from '@playwright/test'

// Runs against the production bundle (vite preview), at /next, the way FastAPI serves it.
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:4174',
    timezoneId: 'America/Chicago',
    colorScheme: 'dark',
  },
  projects: [
    // Spec §4.4: designed at 1440 × 900 and 390 × 844.
    { name: 'desktop', use: { browserName: 'chromium', viewport: { width: 1440, height: 900 } } },
    {
      name: 'phone',
      use: { browserName: 'chromium', viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 1 },
    },
  ],
  webServer: {
    command: 'npm run build && npm run preview',
    url: 'http://localhost:4174/next/',
    reuseExistingServer: false,
  },
})
