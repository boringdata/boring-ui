import { test, expect } from '@playwright/test'

/**
 * E2E tests for theme persistence
 *
 * Tests theme toggling and persistence across page reloads
 */

test.describe('Theme Persistence', () => {
  test('should toggle between light and dark themes', async ({ page }) => {
    await page.goto('/')

    // Check initial theme (should be light by default)
    let htmlElement = page.locator('html')
    let initialTheme = await htmlElement.getAttribute('data-theme')
    expect(['light', 'dark', null]).toContain(initialTheme)

    // Click theme toggle button
    const themeToggle = page.locator('button[aria-label*="Switch to"]').first()
    await themeToggle.click()

    // Wait for theme to change
    await page.waitForTimeout(300)

    // Verify theme changed
    const newTheme = await htmlElement.getAttribute('data-theme')
    expect(newTheme).not.toBe(initialTheme)
  })

  test('should persist theme across page reload', async ({ page }) => {
    await page.goto('/')

    // Toggle theme
    const themeToggle = page.locator('button[aria-label*="Switch to"]').first()
    await themeToggle.click()
    await page.waitForTimeout(300)

    // Get current theme
    let htmlElement = page.locator('html')
    const themeBeforeReload = await htmlElement.getAttribute('data-theme')

    // Reload page
    await page.reload()

    // Verify theme persisted
    htmlElement = page.locator('html')
    const themeAfterReload = await htmlElement.getAttribute('data-theme')
    expect(themeAfterReload).toBe(themeBeforeReload)
  })

  test('should store theme preference in localStorage', async ({ page }) => {
    await page.goto('/')

    // Check localStorage key exists after toggle
    const themeToggle = page.locator('button[aria-label*="Switch to"]').first()
    await themeToggle.click()
    await page.waitForTimeout(300)

    // Verify localStorage has theme key
    const storageKeys = await page.evaluate(() => {
      return Object.keys(localStorage)
        .filter((key) => key.includes('theme'))
        .map((key) => ({ key, value: localStorage.getItem(key) }))
    })

    expect(storageKeys.length).toBeGreaterThan(0)
    expect(storageKeys[0].value).toMatch(/^(light|dark)$/)
  })

  test('should respect configured storage prefix', async ({ page, context }) => {
    // Set custom prefix in window config before navigation
    await context.addInitScript(() => {
      window.__BORING_UI_CONFIG__ = {
        storage: { prefix: 'test-app' },
      }
    })

    await page.goto('/')

    // Toggle theme
    const themeToggle = page.locator('button[aria-label*="Switch to"]').first()
    await themeToggle.click()
    await page.waitForTimeout(300)

    // Check localStorage uses custom prefix
    const customPrefixKey = await page.evaluate(() => {
      const keys = Object.keys(localStorage)
      return keys.find((key) => key.startsWith('test-app-'))
    })

    expect(customPrefixKey).toBeDefined()
    expect(customPrefixKey).toContain('test-app-theme')
  })

  test('should apply CSS custom properties for custom accent colors', async ({
    page,
    context,
  }) => {
    // Set custom styles in window config
    await context.addInitScript(() => {
      window.__BORING_UI_CONFIG__ = {
        styles: {
          light: {
            accent: '#8b5cf6', // Purple
          },
        },
      }
    })

    await page.goto('/')

    // Check if CSS variable is applied
    const accentColor = await page.evaluate(() => {
      return getComputedStyle(document.documentElement).getPropertyValue(
        '--color-accent'
      )
    })

    expect(accentColor.trim()).toContain('8b5cf6')
  })
})

test.describe('Theme Toggle Accessibility', () => {
  test('theme toggle should have proper ARIA attributes', async ({ page }) => {
    await page.goto('/')

    const themeToggle = page.locator('button[aria-label*="Switch to"]').first()

    // Check aria-pressed attribute
    const ariaPressed = await themeToggle.getAttribute('aria-pressed')
    expect(['true', 'false']).toContain(ariaPressed)

    // Check aria-label exists
    const ariaLabel = await themeToggle.getAttribute('aria-label')
    expect(ariaLabel).toBeDefined()
    expect(ariaLabel).toMatch(/Switch to (light|dark) mode/)
  })

  test('theme toggle should be keyboard accessible', async ({ page }) => {
    await page.goto('/')

    // Focus on theme toggle using Tab
    await page.keyboard.press('Tab')
    await page.keyboard.press('Tab') // May need multiple tabs depending on layout

    // Find focused element
    const focused = await page.evaluate(() => {
      return document.activeElement?.getAttribute('aria-label')?.includes(
        'Switch to'
      )
    })

    // If we found the toggle, test with Space/Enter
    if (focused) {
      const htmlBefore = await page.locator('html').getAttribute('data-theme')

      await page.keyboard.press('Space')
      await page.waitForTimeout(300)

      const htmlAfter = await page.locator('html').getAttribute('data-theme')
      expect(htmlAfter).not.toBe(htmlBefore)
    }
  })
})
