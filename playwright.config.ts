import { defineConfig, devices } from '@playwright/test';

/**
 * Милорадове · Playwright config
 * Deterministic static-site smoke + visual regression + axe.
 * Runs against dist/ served by python http.server on :8787.
 */
export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  expect: {
    toHaveScreenshot: {
      // Tolerate hairline sub-pixel differences; strict enough to catch real regressions.
      maxDiffPixelRatio: 0.01,
      threshold: 0.2,
    },
  },
  use: {
    baseURL: 'http://localhost:8787',
    ignoreHTTPSErrors: true,
    trace: 'on-first-retry',
    contextOptions: {
      reducedMotion: 'reduce',  // wave, breathe, ripple → still
    },
  },
  projects: [
    {
      name: 'desktop',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 900 },
        // Chromium-only flag for screenshot stability; webkit rejects it.
        launchOptions: { args: ['--disable-gpu-compositing'] },
      },
    },
    { name: 'mobile', use: { ...devices['iPhone 13'] } },
  ],
  webServer: {
    command: 'python3 -m http.server 8787 --directory dist',
    url: 'http://localhost:8787/index.html',
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
