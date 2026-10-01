import { defineConfig } from '@playwright/test'
import base from './playwright.config'

// §14 Performance, measured in the browser: `npm run e2e:perf` runs e2e/stage.perf.ts on e2e's own
// projects and mock build. The stage's frame rate is a GPU's, so Chromium draws on this machine's GPU
// (ANGLE over Vulkan) instead of the software renderer Playwright uses by default; the test fails if
// it fell back to software anyway. One test at a time, so none measures another's load. It serves
// the mock build on e2e's port, so it can't run beside `npm run e2e`.
const GPU = ['--use-angle=vulkan', '--enable-features=Vulkan', '--ignore-gpu-blocklist']

export default defineConfig({
  ...base,
  testMatch: '*.perf.ts',
  fullyParallel: false,
  workers: 1,
  projects: base.projects?.map((project) => ({ ...project, use: { ...project.use, launchOptions: { args: GPU } } })),
  // The mock build only; the production bundle isn't measured.
  webServer: [base.webServer ?? []].flat()[0],
})
