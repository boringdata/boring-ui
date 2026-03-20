import { expect, test } from '@playwright/test'
import type { Page, Route } from '@playwright/test'

const json = (value: unknown) => JSON.stringify(value)

const fulfillJson = (route: Route, status: number, body: unknown) => {
  route.fulfill({
    status,
    contentType: 'application/json',
    body: json(body),
  })
}

const waitForUserMenuButton = async (page: Page) => {
  await page.waitForSelector('[data-testid="dockview"]', { timeout: 20000 })
  const button = page.locator('[aria-label="User menu"]').first()
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      await button.waitFor({ state: 'visible', timeout: 10000 })
      return button
    } catch (error) {
      if (attempt === 2) throw error
      await page.reload()
      await page.waitForSelector('[data-testid="dockview"]', { timeout: 20000 })
    }
  }
  return button
}

const stubAppBootstrap = async (page: Page) => {
  await page.route('**/__bui/config', (route) =>
    fulfillJson(route, 200, {
      app: { id: 'boring-ui', name: 'Boring UI', logo: 'B' },
      frontend: {
        branding: { name: 'Boring UI', logo: 'B' },
        data: { backend: 'lightningfs' },
        agents: { mode: 'frontend' },
        mode: { profile: 'frontend' },
      },
      agents: { mode: 'frontend', default: 'pi', available: ['pi'] },
      auth: { provider: 'local' },
    }),
  )
  await page.route('**/api/capabilities', (route) =>
    fulfillJson(route, 200, {
      version: 'test',
      features: {
        files: true,
        git: true,
        pty: true,
        chat_claude_code: true,
        approval: true,
        pi: true,
      },
      routers: [],
    }),
  )
}

test.describe('Canonical Transport Regression', () => {
  test('user menu bootstrap + logout use canonical control-plane routes', async ({ page }) => {
    const apiPaths = new Set<string>()

    page.on('request', (request) => {
      const url = new URL(request.url())
      if (url.pathname.startsWith('/api/') || url.pathname === '/auth/logout') {
        apiPaths.add(url.pathname)
      }
    })

    await stubAppBootstrap(page)
    await page.route('**/auth/logout', (route) => {
      route.fulfill({
        status: 204,
        body: '',
      })
    })
    await page.route('**/api/v1/me', (route) =>
      fulfillJson(route, 200, { email: 'john@example.com', user_id: 'user-1' }),
    )
    await page.route('**/api/v1/workspaces', (route) =>
      fulfillJson(route, 200, { workspaces: [{ id: 'ws-1', name: 'One' }] }),
    )

    await page.goto('/')
    const userMenuButton = await waitForUserMenuButton(page)

    await expect.poll(() => apiPaths.has('/api/v1/me')).toBe(true)
    await expect.poll(() => apiPaths.has('/api/v1/workspaces')).toBe(true)
    expect(Array.from(apiPaths)).not.toContain('/api/me')
    expect(Array.from(apiPaths)).not.toContain('/api/workspaces')

    const logoutRequest = page.waitForRequest(
      (request) => new URL(request.url()).pathname === '/auth/logout',
    )
    await userMenuButton.click()
    const logoutMenuItem = page.getByRole('menuitem', { name: 'Logout' })
    await expect(logoutMenuItem).toBeEnabled()
    await logoutMenuItem.click()
    await logoutRequest
  })
})
