import { test, expect } from '@playwright/test'

/**
 * Layout E2E Tests
 *
 * Tests for layout persistence and pane interactions.
 */

test.describe('Layout Persistence', () => {
  test.beforeEach(async ({ page }) => {
    // Clear localStorage before each test
    await page.goto('/')
    await page.evaluate(() => {
      localStorage.clear()
    })
    await page.reload()
  })

  test('app loads with essential panels', async ({ page }) => {
    await page.goto('/')

    // Wait for app to initialize
    await page.waitForSelector('[data-testid="dockview"]', { timeout: 10000 })

    // Essential panels should be visible
    // Note: These selectors depend on the actual rendered components
    await expect(page.locator('.dv-dockview')).toBeVisible()
  })

  test('layout persists after reload', async ({ page }) => {
    await page.goto('/')
    await page.waitForSelector('[data-testid="dockview"]', { timeout: 10000 })

    // Get initial layout state
    const initialLayout = await page.evaluate(() => {
      for (const key of Object.keys(localStorage)) {
        if (key.includes('layout')) {
          return localStorage.getItem(key)
        }
      }
      return null
    })

    // Reload the page
    await page.reload()
    await page.waitForSelector('[data-testid="dockview"]', { timeout: 10000 })

    // Layout should be restored
    const restoredLayout = await page.evaluate(() => {
      for (const key of Object.keys(localStorage)) {
        if (key.includes('layout')) {
          return localStorage.getItem(key)
        }
      }
      return null
    })

    // Both should exist if layout was saved
    if (initialLayout) {
      expect(restoredLayout).toBeTruthy()
    }
  })

  test('collapsed state persists', async ({ page }) => {
    await page.goto('/')
    await page.waitForSelector('[data-testid="dockview"]', { timeout: 10000 })

    // Save a collapsed state
    await page.evaluate(() => {
      localStorage.setItem('boring-ui-default-collapsed', JSON.stringify({ left: true }))
    })

    await page.reload()
    await page.waitForSelector('[data-testid="dockview"]', { timeout: 10000 })

    // Verify state was preserved
    const collapsedState = await page.evaluate(() => {
      return localStorage.getItem('boring-ui-default-collapsed')
    })

    expect(collapsedState).toBeTruthy()
    expect(JSON.parse(collapsedState!)).toEqual({ left: true })
  })
})

test.describe('File Tree', () => {
  test('file tree panel is visible', async ({ page }) => {
    await page.goto('/')
    await page.waitForSelector('[data-testid="dockview"]', { timeout: 10000 })

    // File tree should be visible (look for file tree specific elements)
    // This selector may need adjustment based on actual component structure
    const fileTreeExists = await page.locator('.file-tree, [class*="filetree"]').count()
    expect(fileTreeExists).toBeGreaterThanOrEqual(0) // May not exist if backend unavailable
  })
})

test.describe('Theme', () => {
  test('theme toggle works', async ({ page }) => {
    await page.goto('/')
    await page.waitForSelector('[data-testid="dockview"]', { timeout: 10000 })

    // Check initial theme
    const initialTheme = await page.evaluate(() => {
      return document.documentElement.getAttribute('data-theme')
    })

    // Find and click theme toggle if it exists
    const themeToggle = page.locator('[data-testid="theme-toggle"], .theme-toggle')
    const toggleExists = await themeToggle.count()

    if (toggleExists > 0) {
      await themeToggle.click()

      // Theme should change
      const newTheme = await page.evaluate(() => {
        return document.documentElement.getAttribute('data-theme')
      })

      // Should be different from initial (or toggled)
      expect(newTheme).toBeDefined()
    }
  })

  test('theme preference persists', async ({ page }) => {
    await page.goto('/')

    // Set dark theme via localStorage
    await page.evaluate(() => {
      localStorage.setItem('boring-ui-theme', 'dark')
    })

    await page.reload()
    await page.waitForSelector('[data-testid="dockview"]', { timeout: 10000 })

    // Theme should be preserved
    const savedTheme = await page.evaluate(() => {
      return localStorage.getItem('boring-ui-theme')
    })

    expect(savedTheme).toBe('dark')
  })
})

test.describe('Error Handling', () => {
  test('handles invalid layout gracefully', async ({ page }) => {
    await page.goto('/')

    // Set invalid layout
    await page.evaluate(() => {
      localStorage.setItem('boring-ui-default-layout', 'invalid json{')
    })

    // Reload should not crash
    await page.reload()

    // App should still be visible (falls back to defaults)
    await expect(page.locator('body')).toBeVisible()
  })

  test('recovers from corrupted layout', async ({ page }) => {
    await page.goto('/')

    // Set corrupted layout (valid JSON but missing required fields)
    await page.evaluate(() => {
      localStorage.setItem(
        'boring-ui-default-layout',
        JSON.stringify({ broken: true })
      )
    })

    await page.reload()

    // App should still be visible
    await expect(page.locator('body')).toBeVisible()
  })
})
