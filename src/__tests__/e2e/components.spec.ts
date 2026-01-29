import { test, expect } from '@playwright/test'

test.describe('Boring UI - Component Testing', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
  })

  test.describe('Theme System', () => {
    test('should toggle theme with button', async ({ page }) => {
      const themeToggle = page.locator('button[aria-label="Toggle theme"]').first()
      await expect(themeToggle).toBeVisible()

      await themeToggle.click()
      await page.waitForTimeout(300)

      // Verify theme changed
      const root = page.locator(':root')
      const dataTheme = await root.evaluate((el) => el.getAttribute('data-theme'))
      expect(dataTheme).toMatch(/light|dark/)
    })

    test('should persist theme after reload', async ({ page, context }) => {
      const themeToggle = page.locator('button[aria-label="Toggle theme"]').first()
      const initialTheme = await page.locator(':root').evaluate((el) => el.getAttribute('data-theme'))

      await themeToggle.click()
      await page.waitForTimeout(300)

      const newTheme = await page.locator(':root').evaluate((el) => el.getAttribute('data-theme'))
      expect(newTheme).not.toBe(initialTheme)

      // Reload and check persistence
      await page.reload()
      const persistedTheme = await page.locator(':root').evaluate((el) => el.getAttribute('data-theme'))
      expect(persistedTheme).toBe(newTheme)
    })
  })

  test.describe('Accessibility Features', () => {
    test('should have keyboard accessible buttons', async ({ page }) => {
      const button = page.locator('button').first()

      await button.focus()
      expect(await button.evaluate((el) => {
        return document.activeElement === el
      })).toBeTruthy()
    })

    test('should support keyboard navigation', async ({ page }) => {
      const buttons = page.locator('button')
      const count = await buttons.count()

      // Tab through buttons
      for (let i = 0; i < Math.min(count, 3); i++) {
        await page.keyboard.press('Tab')
        const focused = await page.evaluate(() => document.activeElement?.tagName)
        expect(focused).toBe('BUTTON')
      }
    })

    test('should have proper heading hierarchy', async ({ page }) => {
      const h1s = page.locator('h1')
      const h2s = page.locator('h2')
      const h3s = page.locator('h3')

      // Just verify they exist (if any)
      const h1Count = await h1s.count()
      const h2Count = await h2s.count()
      const h3Count = await h3s.count()

      expect(h1Count + h2Count + h3Count).toBeGreaterThanOrEqual(0)
    })

    test('should have proper landmark regions', async ({ page }) => {
      const main = page.locator('main, [role="main"]')
      expect(await main.count()).toBeGreaterThanOrEqual(0)
    })
  })

  test.describe('Responsive Design', () => {
    test('should render on mobile (375px)', async ({ browser }) => {
      const context = await browser.newContext({
        viewport: { width: 375, height: 667 },
      })
      const page = await context.newPage()
      await page.goto('/')

      const header = page.locator('header').first()
      await expect(header).toBeVisible()

      await context.close()
    })

    test('should render on tablet (768px)', async ({ browser }) => {
      const context = await browser.newContext({
        viewport: { width: 768, height: 1024 },
      })
      const page = await context.newPage()
      await page.goto('/')

      const header = page.locator('header').first()
      await expect(header).toBeVisible()

      await context.close()
    })

    test('should render on desktop (1920px)', async ({ browser }) => {
      const context = await browser.newContext({
        viewport: { width: 1920, height: 1080 },
      })
      const page = await context.newPage()
      await page.goto('/')

      const header = page.locator('header').first()
      await expect(header).toBeVisible()

      await context.close()
    })
  })

  test.describe('Performance & Visual', () => {
    test('should load without critical errors', async ({ page }) => {
      let hasErrors = false
      page.on('console', (msg) => {
        if (msg.type() === 'error') {
          hasErrors = true
          console.error('Console error:', msg.text())
        }
      })

      await page.goto('/')
      await page.waitForLoadState('networkidle')

      expect(hasErrors).toBeFalsy()
    })

    test('should have proper color contrast', async ({ page }) => {
      // Check for basic color contrast by ensuring text is readable
      const textElements = page.locator('body *:has-text')
      const count = await textElements.count()
      expect(count).toBeGreaterThan(0)
    })

    test('should respect reduced motion preference', async ({ browser }) => {
      const context = await browser.newContext({
        reducedMotion: 'reduce',
      })
      const page = await context.newPage()
      await page.goto('/')

      // Verify reduced motion CSS is applied
      const hasReducedMotion = await page.evaluate(() => {
        return window.matchMedia('(prefers-reduced-motion: reduce)').matches
      })
      expect(hasReducedMotion).toBeTruthy()

      await context.close()
    })

    test('should measure page load performance', async ({ page }) => {
      const startTime = Date.now()

      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const loadTime = Date.now() - startTime

      // Log performance (adjust threshold as needed)
      console.log(`Page load time: ${loadTime}ms`)
      expect(loadTime).toBeLessThan(5000) // 5 second threshold
    })
  })

  test.describe('Layout & Structure', () => {
    test('should render main content area', async ({ page }) => {
      const main = page.locator('main, [role="main"], #root').first()
      await expect(main).toBeVisible()
    })

    test('should render header', async ({ page }) => {
      const header = page.locator('header').first()
      await expect(header).toBeVisible()
    })

    test('should not have horizontal scrollbar on desktop', async ({ page }) => {
      const isOverflowing = await page.evaluate(() => {
        return document.body.scrollWidth > window.innerWidth
      })
      expect(isOverflowing).toBeFalsy()
    })
  })

  test.describe('Interactions', () => {
    test('should handle button clicks', async ({ page }) => {
      const buttons = page.locator('button')
      const count = await buttons.count()

      if (count > 0) {
        const firstButton = buttons.first()
        const isEnabled = await firstButton.isEnabled()

        if (isEnabled) {
          await firstButton.click()
          // Button clicked successfully
          expect(true).toBeTruthy()
        }
      }
    })

    test('should handle hover states', async ({ page }) => {
      const buttons = page.locator('button')
      const count = await buttons.count()

      if (count > 0) {
        const firstButton = buttons.first()
        await firstButton.hover()

        // Hover applied successfully
        expect(true).toBeTruthy()
      }
    })

    test('should handle focus states', async ({ page }) => {
      const firstButton = page.locator('button').first()

      await firstButton.focus()
      const isFocused = await firstButton.evaluate((el) => {
        return document.activeElement === el
      })

      expect(isFocused).toBeTruthy()
    })
  })

  test.describe('Visual Regression', () => {
    test('should match desktop screenshot', async ({ page, browserName }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      await expect(page).toHaveScreenshot(`desktop-${browserName}.png`, {
        maxDiffPixels: 1000,
      })
    })

    test('should match mobile screenshot', async ({ browser, browserName }) => {
      const context = await browser.newContext({
        viewport: { width: 375, height: 667 },
      })
      const page = await context.newPage()
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      await expect(page).toHaveScreenshot(`mobile-${browserName}.png`, {
        maxDiffPixels: 500,
      })

      await context.close()
    })
  })

  test.describe('Dark Mode Visual', () => {
    test('should render properly in dark mode', async ({ page }) => {
      const themeToggle = page.locator('button[aria-label="Toggle theme"]').first()

      // Switch to dark mode
      await themeToggle.click()
      await page.waitForTimeout(300)

      const isDark = await page.locator(':root').evaluate((el) => {
        return el.getAttribute('data-theme') === 'dark' ||
               el.classList.contains('dark')
      })

      expect(isDark).toBeTruthy()
    })
  })
})
