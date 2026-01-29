import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright E2E Test Configuration
 *
 * To install Playwright:
 * npm install -D @playwright/test
 *
 * To run tests:
 * npm run test:e2e
 */

export default defineConfig({
  testDir: './src/__tests__/e2e',
  testMatch: '**/*.spec.ts',

  // Timeout for each test
  timeout: 30000,

  // Timeout for entire test run
  globalTimeout: 600000,

  // Run tests in parallel
  fullyParallel: true,

  // Fail on console errors
  forbidOnly: !!process.env.CI,

  // Retry failing tests
  retries: process.env.CI ? 2 : 0,

  // Number of workers
  workers: process.env.CI ? 1 : undefined,

  // Reporter configurations
  reporter: [
    ['html', { open: 'never' }],
    ['json', { outputFile: 'test-results/results.json' }],
    ['junit', { outputFile: 'test-results/junit.xml' }],
  ],

  // Shared settings for all browsers
  use: {
    // Base URL for requests
    baseURL: 'http://localhost:5173',

    // Take screenshot on failure
    screenshot: 'only-on-failure',

    // Record traces for debugging
    trace: 'on-first-retry',

    // Video on failure
    video: 'retain-on-failure',
  },

  // Configure different browsers
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },

    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },

    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },

    // Mobile testing
    {
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 5'] },
    },
  ],

  // Web Server configuration for running tests against dev server
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
})
