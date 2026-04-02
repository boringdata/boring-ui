import { test, expect } from '@playwright/test'
import type { Page, Route } from '@playwright/test'

/**
 * Chat-Centered Layout E2E Smoke Tests
 *
 * Validates the chat-centered shell layout end-to-end using stubbed
 * backend responses (no real backend needed). Tests cover:
 *   - Shell rendering (workspace, nav rail, empty state)
 *   - NavRail interactions (new chat, history drawer, surface toggle)
 *   - Composer functionality (input, send button)
 *   - Layout switcher (chat-centered vs legacy)
 *   - FileTree presence inside the Surface
 */

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
  // Stub the tree endpoint used by Surface explorer file tree
  await page.route('**/api/tree**', (route) =>
    fulfillJson(route, 200, [
      { name: 'README.md', path: 'README.md', is_dir: false },
      { name: 'src', path: 'src', is_dir: true },
    ]),
  )
}

const waitForChatWorkspace = async (page: Page) => {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      await page.waitForSelector('[data-testid="chat-centered-workspace"]', {
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

test.describe('Chat-Centered Layout', () => {
  test.describe.configure({ timeout: 60_000 })

  test.beforeEach(async ({ page }) => {
    await stubAppBootstrap(page, { dataBackend: 'lightningfs' })
    // Clear storage
    await page.goto('/')
    await page.evaluate(() => {
      localStorage.clear()
      sessionStorage.clear()
    })
  })

  test('chat layout renders with workspace container', async ({ page }) => {
    await page.goto('/?shell=chat-centered', {
      waitUntil: 'domcontentloaded',
      timeout: 60000,
    })
    await waitForChatWorkspace(page)

    await expect(
      page.locator('[data-testid="chat-centered-workspace"]'),
    ).toBeVisible({ timeout: 20000 })
  })

  test('nav rail is present with brand, new-chat, history, and surface buttons', async ({
    page,
  }) => {
    await page.goto('/?shell=chat-centered', {
      waitUntil: 'domcontentloaded',
      timeout: 60000,
    })
    await waitForChatWorkspace(page)

    const navRail = page.locator('[data-testid="nav-rail"]')
    await expect(navRail).toBeVisible({ timeout: 20000 })

    await expect(page.locator('[data-testid="nav-rail-brand"]')).toBeVisible({
      timeout: 20000,
    })
    await expect(
      page.locator('[data-testid="nav-rail-new-chat"]'),
    ).toBeVisible({ timeout: 20000 })
    await expect(
      page.locator('[data-testid="nav-rail-history"]'),
    ).toBeVisible({ timeout: 20000 })
    await expect(
      page.locator('[data-testid="nav-rail-surface"]'),
    ).toBeVisible({ timeout: 20000 })
  })

  test('empty state shows welcome message', async ({ page }) => {
    await page.goto('/?shell=chat-centered', {
      waitUntil: 'domcontentloaded',
      timeout: 60000,
    })
    await waitForChatWorkspace(page)

    // Empty state should appear when there are no messages
    const emptyState = page.locator('.vc-stage-empty, .vc-stage-empty-title')
    await expect(emptyState.first()).toBeVisible({ timeout: 20000 })
  })

  test('new chat button resets to empty state', async ({ page }) => {
    await page.goto('/?shell=chat-centered', {
      waitUntil: 'domcontentloaded',
      timeout: 60000,
    })
    await waitForChatWorkspace(page)

    // Verify empty state is present initially
    await expect(page.locator('.vc-stage-empty').first()).toBeVisible({
      timeout: 20000,
    })

    // Click new chat button
    await page.locator('[data-testid="nav-rail-new-chat"]').click()

    // Empty state should still be visible (fresh session)
    await expect(page.locator('.vc-stage-empty').first()).toBeVisible({
      timeout: 20000,
    })
  })

  test('sessions drawer toggles open and closed', async ({ page }) => {
    await page.goto('/?shell=chat-centered', {
      waitUntil: 'domcontentloaded',
      timeout: 60000,
    })
    await waitForChatWorkspace(page)

    const historyBtn = page.locator('[data-testid="nav-rail-history"]')
    const drawer = page.locator('[data-testid="browse-drawer"]')

    // Drawer should not be visible initially
    await expect(drawer).not.toBeVisible()

    // Click history button to open drawer
    await historyBtn.click()
    await expect(drawer).toBeVisible({ timeout: 20000 })

    // Click again to close drawer
    await historyBtn.click()
    await expect(drawer).not.toBeVisible({ timeout: 20000 })
  })

  test('surface toggle opens and closes the surface panel', async ({
    page,
  }) => {
    await page.goto('/?shell=chat-centered', {
      waitUntil: 'domcontentloaded',
      timeout: 60000,
    })
    await waitForChatWorkspace(page)

    const surfaceBtn = page.locator('[data-testid="nav-rail-surface"]')

    // Surface starts collapsed — full surface-shell is not visible
    await expect(
      page.locator('[data-testid="surface-shell"]'),
    ).not.toBeVisible()

    // Click surface button to expand
    await surfaceBtn.click()
    await expect(page.locator('[data-testid="surface-shell"]')).toBeVisible({
      timeout: 20000,
    })

    // Click again to collapse
    await surfaceBtn.click()
    await expect(
      page.locator('[data-testid="surface-shell"]'),
    ).not.toBeVisible({ timeout: 20000 })
  })

  test('composer input exists and can receive text', async ({ page }) => {
    await page.goto('/?shell=chat-centered', {
      waitUntil: 'domcontentloaded',
      timeout: 60000,
    })
    await waitForChatWorkspace(page)

    const input = page.locator('.vc-composer-input')
    await expect(input).toBeVisible({ timeout: 20000 })

    // Type into the composer
    await input.fill('Hello, world!')
    await expect(input).toHaveValue('Hello, world!')

    // Send button should exist
    const sendBtn = page.locator(
      '[data-testid="chat-send-btn"], .vc-composer button[type="submit"], .vc-composer-send',
    )
    await expect(sendBtn.first()).toBeVisible({ timeout: 20000 })
  })

  test('legacy shell renders dockview instead of chat workspace', async ({
    page,
  }) => {
    await page.goto('/?shell=legacy', {
      waitUntil: 'domcontentloaded',
      timeout: 60000,
    })
    await waitForDockview(page)

    // Dockview should render
    await expect(page.locator('[data-testid="dockview"]')).toBeVisible({
      timeout: 20000,
    })

    // Chat workspace should NOT render
    await expect(
      page.locator('[data-testid="chat-centered-workspace"]'),
    ).toHaveCount(0)
  })

  test('surface contains file tree when opened', async ({ page }) => {
    await page.goto('/?shell=chat-centered', {
      waitUntil: 'domcontentloaded',
      timeout: 60000,
    })
    await waitForChatWorkspace(page)

    // Open the surface
    await page.locator('[data-testid="nav-rail-surface"]').click()
    await expect(page.locator('[data-testid="surface-shell"]')).toBeVisible({
      timeout: 20000,
    })

    // The Surface explorer contains a file tree section
    const fileTree = page.locator(
      '.sf-explorer-filetree, .file-tree, [class*="filetree"]',
    )
    await expect(fileTree.first()).toBeVisible({ timeout: 20000 })
  })
})
