import { test, expect } from '@playwright/test'

/**
 * Shared Tool Renderer Visual Regression Tests
 *
 * Uses the fixture page at /fixture-renderers.html which renders all shared
 * renderers with deterministic data. Tests verify structure and take
 * screenshots for baseline comparison.
 */

const FIXTURE_URL = '/fixture-renderers.html'

test.describe('Shared Tool Renderers', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(FIXTURE_URL)
    await page.waitForSelector('[data-testid="renderer-showcase"]', { timeout: 10000 })
  })

  // ─── Full Page ───────────────────────────────────────────────────

  test('fixture page renders all sections', async ({ page }) => {
    const sections = [
      'section-bash',
      'section-read',
      'section-write',
      'section-edit',
      'section-grep',
      'section-glob',
      'section-generic',
      'section-context',
    ]
    for (const id of sections) {
      await expect(page.locator(`[data-testid="${id}"]`)).toBeAttached()
    }
  })

  test('full page screenshot', async ({ page }) => {
    await expect(page).toHaveScreenshot('renderers-full-page.png', {
      fullPage: true,
      maxDiffPixelRatio: 0.01,
    })
  })

  // ─── Bash Renderer ──────────────────────────────────────────────

  test.describe('Bash Renderer', () => {
    test('renders success with command and output', async ({ page }) => {
      const fixture = page.locator('[data-testid="fixture-bash-success"]')
      await expect(fixture.locator('.tool-use-name')).toHaveText('Bash')
      await expect(fixture.locator('code')).toContainText('ls -la src/')
      await expect(fixture.locator('.tool-output')).toContainText('total 32')
    })

    test('renders error with red styling', async ({ page }) => {
      const fixture = page.locator('[data-testid="fixture-bash-error"]')
      await expect(fixture.locator('.tool-error')).toContainText('No such file or directory')
    })

    test('renders running state', async ({ page }) => {
      const fixture = page.locator('[data-testid="fixture-bash-running"]')
      await expect(fixture).toContainText('Running command...')
    })

    test('renders long output with expand button', async ({ page }) => {
      const fixture = page.locator('[data-testid="fixture-bash-long"]')
      await expect(fixture.locator('button')).toContainText('more lines')
    })

    test('screenshot', async ({ page }) => {
      const section = page.locator('[data-testid="section-bash"]')
      await expect(section).toHaveScreenshot('bash-renderer.png', {
        maxDiffPixelRatio: 0.01,
      })
    })
  })

  // ─── Read Renderer ──────────────────────────────────────────────

  test.describe('Read Renderer', () => {
    test('renders file content', async ({ page }) => {
      const fixture = page.locator('[data-testid="fixture-read-success"]')
      await expect(fixture.locator('.tool-use-name')).toHaveText('Read')
      await expect(fixture.locator('.tool-use-description')).toContainText('App.jsx')
      await expect(fixture.locator('.tool-output')).toContainText('Main application')
    })

    test('renders truncated indicator', async ({ page }) => {
      const fixture = page.locator('[data-testid="fixture-read-truncated"]')
      await expect(fixture.locator('.tool-use-description')).toContainText('truncated')
    })

    test('renders error', async ({ page }) => {
      const fixture = page.locator('[data-testid="fixture-read-error"]')
      await expect(fixture.locator('.tool-error')).toContainText('ENOENT')
    })

    test('screenshot', async ({ page }) => {
      const section = page.locator('[data-testid="section-read"]')
      await expect(section).toHaveScreenshot('read-renderer.png', {
        maxDiffPixelRatio: 0.01,
      })
    })
  })

  // ─── Write Renderer ─────────────────────────────────────────────

  test.describe('Write Renderer', () => {
    test('renders written file content', async ({ page }) => {
      const fixture = page.locator('[data-testid="fixture-write-success"]')
      await expect(fixture.locator('.tool-use-name')).toHaveText('Write')
      await expect(fixture.locator('.tool-use-description')).toContainText('config.js')
      await expect(fixture.locator('.tool-output')).toContainText('API_URL')
    })

    test('renders pending state', async ({ page }) => {
      const fixture = page.locator('[data-testid="fixture-write-pending"]')
      await expect(fixture).toContainText('Waiting for permission...')
    })

    test('screenshot', async ({ page }) => {
      const section = page.locator('[data-testid="section-write"]')
      await expect(section).toHaveScreenshot('write-renderer.png', {
        maxDiffPixelRatio: 0.01,
      })
    })
  })

  // ─── Edit Renderer ──────────────────────────────────────────────

  test.describe('Edit Renderer', () => {
    test('renders diff with additions and removals', async ({ page }) => {
      const fixture = page.locator('[data-testid="fixture-edit-diff"]')
      await expect(fixture.locator('.tool-use-name')).toHaveText('Edit')
      await expect(fixture.locator('.tool-use-description')).toContainText('App.jsx')
      // Diff view should have colored lines
      const diffView = fixture.locator('.shared-diff-view')
      await expect(diffView).toBeAttached()
    })

    test('renders old/new comparison', async ({ page }) => {
      const fixture = page.locator('[data-testid="fixture-edit-oldnew"]')
      await expect(fixture).toContainText('utils.js')
    })

    test('renders error', async ({ page }) => {
      const fixture = page.locator('[data-testid="fixture-edit-error"]')
      await expect(fixture.locator('.tool-error')).toContainText('Permission denied')
    })

    test('screenshot', async ({ page }) => {
      const section = page.locator('[data-testid="section-edit"]')
      await expect(section).toHaveScreenshot('edit-renderer.png', {
        maxDiffPixelRatio: 0.01,
      })
    })
  })

  // ─── Grep Renderer ──────────────────────────────────────────────

  test.describe('Grep Renderer', () => {
    test('renders search results grouped by file', async ({ page }) => {
      const fixture = page.locator('[data-testid="fixture-grep-success"]')
      await expect(fixture.locator('.tool-use-name')).toHaveText('Grep')
      await expect(fixture.locator('.inline-code')).toContainText('useState')
      await expect(fixture).toContainText('src/App.jsx')
      await expect(fixture).toContainText('5 matches in 2 files')
    })

    test('renders no matches', async ({ page }) => {
      const fixture = page.locator('[data-testid="fixture-grep-empty"]')
      await expect(fixture).toContainText('No matches found')
    })

    test('renders running state', async ({ page }) => {
      const fixture = page.locator('[data-testid="fixture-grep-running"]')
      await expect(fixture).toContainText('Searching...')
    })

    test('highlights pattern matches', async ({ page }) => {
      const fixture = page.locator('[data-testid="fixture-grep-success"]')
      const marks = fixture.locator('mark')
      await expect(marks.first()).toBeAttached()
    })

    test('screenshot', async ({ page }) => {
      const section = page.locator('[data-testid="section-grep"]')
      await expect(section).toHaveScreenshot('grep-renderer.png', {
        maxDiffPixelRatio: 0.01,
      })
    })
  })

  // ─── Glob Renderer ──────────────────────────────────────────────

  test.describe('Glob Renderer', () => {
    test('renders file list', async ({ page }) => {
      const fixture = page.locator('[data-testid="fixture-glob-success"]')
      await expect(fixture.locator('.tool-use-name')).toHaveText('Glob')
      await expect(fixture).toContainText('src/App.jsx')
      await expect(fixture).toContainText('src/panels/TerminalPanel.jsx')
    })

    test('renders no files found', async ({ page }) => {
      const fixture = page.locator('[data-testid="fixture-glob-empty"]')
      await expect(fixture).toContainText('No files found')
    })

    test('screenshot', async ({ page }) => {
      const section = page.locator('[data-testid="section-glob"]')
      await expect(section).toHaveScreenshot('glob-renderer.png', {
        maxDiffPixelRatio: 0.01,
      })
    })
  })

  // ─── Generic Renderer ───────────────────────────────────────────

  test.describe('Generic Renderer', () => {
    test('renders unknown tool with name and output', async ({ page }) => {
      const fixture = page.locator('[data-testid="fixture-generic-success"]')
      await expect(fixture.locator('.tool-use-name')).toHaveText('WebSearch')
      await expect(fixture.locator('.tool-output')).toContainText('Found 15 results')
    })

    test('renders running state', async ({ page }) => {
      const fixture = page.locator('[data-testid="fixture-generic-running"]')
      await expect(fixture).toContainText('Running...')
    })

    test('screenshot', async ({ page }) => {
      const section = page.locator('[data-testid="section-generic"]')
      await expect(section).toHaveScreenshot('generic-renderer.png', {
        maxDiffPixelRatio: 0.01,
      })
    })
  })

  // ─── ToolResultView (Context) ───────────────────────────────────

  test.describe('ToolResultView via Context', () => {
    test('renders result through ToolRendererProvider', async ({ page }) => {
      const fixture = page.locator('[data-testid="fixture-context-view"]')
      await expect(fixture.locator('.tool-use-name')).toHaveText('Bash')
      await expect(fixture).toContainText('rendered via ToolResultView')
    })

    test('screenshot', async ({ page }) => {
      const section = page.locator('[data-testid="section-context"]')
      await expect(section).toHaveScreenshot('context-renderer.png', {
        maxDiffPixelRatio: 0.01,
      })
    })
  })

  // ─── Console Errors ─────────────────────────────────────────────

  test('no console errors during render', async ({ page }) => {
    const errors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(msg.text())
      }
    })

    await page.goto(FIXTURE_URL)
    await page.waitForSelector('[data-testid="renderer-showcase"]', { timeout: 10000 })

    // Allow Vite HMR and websocket errors
    const realErrors = errors.filter(
      (e) => !e.includes('WebSocket') && !e.includes('[vite]'),
    )
    expect(realErrors).toHaveLength(0)
  })
})
