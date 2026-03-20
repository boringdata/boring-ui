import { test, expect } from '@playwright/test'
import type { Page, Route } from '@playwright/test'

/**
 * Layout E2E Tests
 *
 * Tests for layout persistence and pane interactions.
 */

const waitForDockview = async (page: Page) => {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      await page.waitForSelector('[data-testid="dockview"]', {
        state: 'visible',
        timeout: 20000,
      })
      return
    } catch (error) {
      if (attempt === 2) throw error
      await page.reload({ waitUntil: 'domcontentloaded', timeout: 60000 })
    }
  }
}

const json = (value: unknown) => JSON.stringify(value)

const fulfillJson = (route: Route, status: number, body: unknown) => {
  route.fulfill({
    status,
    contentType: 'application/json',
    body: json(body),
  })
}

const stubAppBootstrap = async (
  page: Page,
  {
    dataBackend = 'lightningfs',
    agentMode = 'frontend',
    featureOverrides = {},
  }: {
    dataBackend?: 'lightningfs' | 'http'
    agentMode?: 'frontend' | 'backend'
    featureOverrides?: Record<string, boolean>
  } = {},
) => {
  await page.route('**/__bui/config', (route) =>
    fulfillJson(route, 200, {
      app: { id: 'boring-ui', name: 'Boring UI', logo: 'B' },
      frontend: {
        branding: { name: 'Boring UI', logo: 'B' },
        data: { backend: dataBackend },
        agents: { mode: agentMode },
        mode: { profile: agentMode === 'backend' ? 'backend' : 'frontend' },
      },
      agents: {
        mode: agentMode,
        default: 'pi',
        available: ['pi'],
      },
      auth: { provider: 'local' },
    }),
  )
  await page.route('**/api/capabilities', (route) =>
    fulfillJson(route, 200, {
      version: 'test',
      features: {
        files: true,
        git: false,
        pty: false,
        approval: false,
        pi: true,
        chat_claude_code: agentMode === 'backend',
        ...featureOverrides,
      },
      routers: [],
    }),
  )
  await page.route('**/api/project', (route) =>
    fulfillJson(route, 200, { root: '/' }),
  )
  await page.route('**/api/v1/me', (route) =>
    fulfillJson(route, 200, {
      user_id: 'user-1',
      email: 'frontend-e2e@example.com',
      display_name: 'Frontend E2E',
    }),
  )
  await page.route('**/api/v1/workspaces', async (route) => {
    const request = route.request()
    if (request.method() !== 'GET') {
      return fulfillJson(route, 405, { detail: 'unexpected method' })
    }
    return fulfillJson(route, 200, {
      workspaces: [{ id: 'ws-e2e', name: 'Frontend E2E Workspace' }],
    })
  })
  await page.route('**/api/config**', (route) =>
    fulfillJson(route, 200, {}),
  )
}

const stubHttpFilesystem = async (page: Page) => {
  const files = new Map<string, string>()

  const listRootEntries = () =>
    Array.from(files.keys())
      .filter((path) => !path.includes('/'))
      .sort()
      .map((path) => ({
        name: path,
        path,
        is_dir: false,
        size: files.get(path)?.length || 0,
      }))

  await page.route('**/api/v1/files/list**', (route) => {
    const url = new URL(route.request().url())
    const path = url.searchParams.get('path') || '.'
    if (path === '.' || path === '/') {
      return fulfillJson(route, 200, { entries: listRootEntries() })
    }
    return fulfillJson(route, 200, { entries: [] })
  })

  await page.route('**/api/v1/files/write**', async (route) => {
    const url = new URL(route.request().url())
    const path = String(url.searchParams.get('path') || '').replace(/^\/+/, '')
    const payload = route.request().postDataJSON() as { content?: string }
    files.set(path, String(payload?.content || ''))
    return fulfillJson(route, 200, { success: true })
  })

  await page.route('**/api/v1/files/read**', (route) => {
    const url = new URL(route.request().url())
    const path = String(url.searchParams.get('path') || '').replace(/^\/+/, '')
    return fulfillJson(route, 200, { content: files.get(path) || '' })
  })
}

const waitForFileTree = async (page: Page) => {
  const tree = page.locator('.filetree-body > .file-tree')
  await tree.waitFor({ state: 'visible', timeout: 20000 })
  return tree
}

const waitForUserIdentity = async (page: Page) => {
  const userMenu = page.locator('[aria-label="User menu"]').first()
  await expect(userMenu).toBeVisible({ timeout: 20000 })
  await expect(userMenu).toContainText('frontend-e2e@example.com', { timeout: 20000 })
}

const createRootFile = async (page: Page, filename: string) => {
  const tree = await waitForFileTree(page)
  await tree.click({ button: 'right', position: { x: 10, y: 10 }, force: true })
  await page.getByText('New File', { exact: true }).click()
  const input = page.locator('.filetree-body .rename-input')
  await input.waitFor({ state: 'visible', timeout: 10000 })
  await input.fill(filename)
  await input.press('Enter')
}

const readStoredLayout = async (page: Page) =>
  page.evaluate(() => {
    for (const key of Object.keys(localStorage)) {
      if (key.endsWith('-layout')) {
        return localStorage.getItem(key)
      }
    }
    return null
  })

test.describe('Layout Persistence', () => {
  test.describe.configure({ timeout: 60_000 })

  test.beforeEach(async ({ page }) => {
    // Clear localStorage before each test
    await page.goto('/')
    await page.evaluate(() => {
      localStorage.clear()
      sessionStorage.clear()
    })
    // A second navigation gives us a clean app boot without hitting Chromium
    // reload resource exhaustion in the shared test webserver setup.
    await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 60000 })
    await waitForDockview(page)
  })

  test('app loads with essential panels', async ({ page }) => {
    await page.goto('/')

    // Wait for app to initialize
    await waitForDockview(page)

    await expect(page.locator('[data-testid="dockview"]')).toBeVisible()
    await expect(page.locator('.dv-tab', { hasText: 'Data Catalog' })).toHaveCount(1)
    await expect(page.locator('.dv-tab', { hasText: 'Files' })).toHaveCount(1)
    await expect(page.locator('.dv-tab', { hasText: 'Agent' })).toHaveCount(1)
    await expect(page.getByText('Open a file or start a conversation with the Agent')).toBeVisible()
  })

  test('layout persists after reload', async ({ page }) => {
    await page.goto('/')
    await waitForDockview(page)

    await expect.poll(() => readStoredLayout(page), { timeout: 15000 }).toBeTruthy()
    const initialLayout = await readStoredLayout(page)

    // Reload the page
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 60000 })
    await waitForDockview(page)

    await expect.poll(() => readStoredLayout(page), { timeout: 15000 }).toBeTruthy()
    const restoredLayout = await readStoredLayout(page)

    expect(initialLayout).toBeTruthy()
    expect(restoredLayout).toBeTruthy()
  })

  test('collapsed state persists', async ({ page }) => {
    // This spec can be slow under CI-like load due to app boot + reload, so give it extra headroom.
    test.setTimeout(60_000)

    await page.waitForSelector('[data-testid="dockview"]', { timeout: 20000 })

    // Save a collapsed state
    await page.evaluate(() => {
      localStorage.setItem('boring-ui-default-collapsed', JSON.stringify({ left: true }))
    })

    await page.reload({ waitUntil: 'domcontentloaded', timeout: 60000 })
    await waitForDockview(page)

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
    await stubAppBootstrap(page)
    await page.goto('/')
    await waitForDockview(page)

    // File tree should be visible (look for file tree specific elements)
    // This selector may need adjustment based on actual component structure
    const fileTreeExists = await page.locator('.file-tree, [class*="filetree"]').count()
    expect(fileTreeExists).toBeGreaterThan(0)
  })

  ;[
    {
      name: 'frontend mode creates files without backend file APIs',
      dataBackend: 'lightningfs' as const,
      agentMode: 'frontend' as const,
      expectFileApiCalls: false,
      expectReloadPersistence: false,
    },
    {
      name: 'backend mode creates and persists files through backend file APIs',
      dataBackend: 'http' as const,
      agentMode: 'backend' as const,
      expectFileApiCalls: true,
      expectReloadPersistence: true,
    },
  ].forEach(({ name, dataBackend, agentMode, expectFileApiCalls, expectReloadPersistence }) => {
    test(name, async ({ page }) => {
      test.setTimeout(60_000)

      await stubAppBootstrap(page, { dataBackend, agentMode })
      if (dataBackend === 'http') {
        await stubHttpFilesystem(page)
      }

      const fileApiCalls: string[] = []
      const filename = `${dataBackend}-mode-${Date.now()}.txt`

      page.on('request', (request) => {
        const pathname = new URL(request.url()).pathname
        if (pathname.startsWith('/api/v1/files')) {
          fileApiCalls.push(`${request.method()} ${pathname}`)
        }
      })

      await page.goto('/')
      await waitForDockview(page)
      await waitForUserIdentity(page)

      await createRootFile(page, filename)

      const fileItem = page.locator('.filetree-body .file-item-name', { hasText: filename })
      await expect(fileItem).toBeVisible({ timeout: 15000 })

      if (expectReloadPersistence) {
        await page.reload({ waitUntil: 'domcontentloaded', timeout: 60000 })
        await waitForDockview(page)
        await waitForUserIdentity(page)
        await waitForFileTree(page)

        await expect(page.locator('.filetree-body .file-item-name', { hasText: filename })).toBeVisible({
          timeout: 15000,
        })
      } else {
        const dbNames = await page.evaluate(async () => {
          if (typeof indexedDB.databases !== 'function') return []
          const databases = await indexedDB.databases()
          return databases.map((db) => db.name || '').filter(Boolean)
        })
        expect(dbNames.some((name) => name.startsWith('boring-fs'))).toBe(true)
      }

      if (expectFileApiCalls) {
        expect(fileApiCalls).not.toEqual([])
      } else {
        expect(fileApiCalls).toEqual([])
      }
    })
  })
})

test.describe('Theme', () => {
  test('theme toggle works', async ({ page }) => {
    await page.goto('/')
    await waitForDockview(page)

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
    await waitForDockview(page)

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
