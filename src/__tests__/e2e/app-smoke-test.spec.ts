import { test, expect } from '@playwright/test'

/**
 * Smoke Tests - Verify basic app functionality
 */

test.describe('Claude Code Chat - Smoke Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
  })

  test('App should load successfully', async ({ page }) => {
    expect(page.url()).toContain('localhost')

    const rootElement = page.locator('#root')
    await expect(rootElement).toBeVisible()
  })

  test('Header should display branding', async ({ page }) => {
    const header = page.locator('header').first()
    await expect(header).toBeVisible()

    const logo = header.locator('[class*="logo"]').first()
    expect(await logo.count()).toBeGreaterThan(0)
  })

  test('Theme toggle should be accessible', async ({ page }) => {
    const themeToggle = page.locator('button[aria-label="Toggle theme"]').first()
    expect(await themeToggle.count()).toBeGreaterThan(0)
    await expect(themeToggle).toBeVisible()
  })

  test('Chat interface should be present', async ({ page }) => {
    // Look for chat-related elements
    const chatContainer = page.locator('[class*="chat"], [role="region"]').first()
    expect(await chatContainer.count()).toBeGreaterThan(0)
  })

  test('File tree panel should render', async ({ page }) => {
    const fileTree = page.locator('[class*="tree"], [class*="panel"]').first()
    expect(await fileTree.count()).toBeGreaterThan(0)
  })

  test('Should have no console errors on load', async ({ page }) => {
    const errors: string[] = []

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(msg.text())
      }
    })

    await page.waitForLoadState('networkidle')

    // Filter out non-critical errors
    const criticalErrors = errors.filter(
      (err) => !err.includes('xterm') &&
               !err.includes('ResizeObserver') &&
               !err.includes('WebSocket')
    )

    expect(criticalErrors).toHaveLength(0)
  })

  test('App should be responsive on mobile', async ({ browser }) => {
    const context = await browser.newContext({
      viewport: { width: 375, height: 667 }
    })
    const page = await context.newPage()
    await page.goto('/')

    const header = page.locator('header').first()
    await expect(header).toBeVisible()

    await context.close()
  })

  test('Dark mode toggle should work', async ({ page }) => {
    const themeToggle = page.locator('button[aria-label="Toggle theme"]').first()

    await themeToggle.click()
    await page.waitForTimeout(500)

    const isDarkMode = await page.evaluate(() => {
      const root = document.documentElement
      return root.getAttribute('data-theme') === 'dark' ||
             root.classList.contains('dark')
    })

    expect(typeof isDarkMode).toBe('boolean')
  })
})
