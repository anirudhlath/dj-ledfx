import { defineConfig } from '@playwright/test'

// Runs against the mock build (vite preview --mode mock) at /next, the way FastAPI serves the real
// one: the same bundle, with MSW playing ?scenario= (the hero by default).
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
    command: 'npm run build:mock && npm run preview -- --mode mock',
    url: 'http://localhost:4174/next/',
    reuseExistingServer: false,
  },
})
