import { expect, test } from '@playwright/test'
import type { Page, Route } from '@playwright/test'

import { createRegressionLogger } from './regressionLogging'

const json = (value: unknown) => JSON.stringify(value)

const fulfillJson = (route: Route, status: number, body: unknown) => {
  route.fulfill({
    status,
    contentType: 'application/json',
    body: json(body),
  })
}

const stubAppBootstrap = async (page: Page) => {
  await page.route('**/__bui/config', (route) =>
    fulfillJson(route, 200, { auth: { provider: 'local' } }),
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
        control_plane: true,
      },
      routers: [],
    }),
  )
}

const stubIdentity = async (page: Page, email = 'john@example.com') => {
  await page.route('**/api/v1/me', (route) =>
    fulfillJson(route, 200, { email, user_id: 'user-1' }),
  )
}

const stubWorkspaces = async (
  page: Page,
  {
    status = 200,
    body = { workspaces: [{ id: 'ws-1', name: 'One' }] },
  }: {
    status?: number
    body?: unknown
  } = {},
) => {
  await page.route('**/api/v1/workspaces**', async (route) => {
    const request = route.request()
    if (request.method() !== 'GET') {
      return fulfillJson(route, 405, { detail: 'unexpected method' })
    }
    return fulfillJson(route, status, body)
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
      if (attempt === 2) {
        throw error
      }
      await page.reload()
      await page.waitForSelector('[data-testid="dockview"]', { timeout: 20000 })
    }
  }
  return button
}

test.describe('Phase 1 Regression Logging', () => {
  test.describe.configure({ timeout: 60_000 })
  test.use({ viewport: { width: 1280, height: 1024 } })

  test('keyboard close returns focus to the user menu trigger and preserves a light-theme baseline', async ({ page }, testInfo) => {
    const logger = createRegressionLogger(page, testInfo, {
      flow: 'user-menu-focus-return',
      theme: 'light',
    })

    try {
      await stubAppBootstrap(page)
      await stubIdentity(page)
      await stubWorkspaces(page)

      const userMenuButton = await logger.step('navigate to workspace shell', async () => {
        await page.goto('/w/ws-1/')
        return waitForUserMenuButton(page)
      })

      await logger.step('open the user menu with the keyboard', async () => {
        await userMenuButton.focus()
        await page.keyboard.press('Enter')
        await expect(page.getByRole('menu', { name: 'User menu' })).toBeVisible()
      })

      await logger.note('visual-baseline', { snapshot: 'phase1-user-menu-open-light.png' })
      await logger.step('capture the light-theme open-menu baseline', async () => {
        await expect(page).toHaveScreenshot('phase1-user-menu-open-light.png')
      })

      await logger.step('close the menu and verify focus return', async () => {
        await page.keyboard.press('Escape')
        await expect(page.getByRole('menu', { name: 'User menu' })).toBeHidden()
        await expect(userMenuButton).toBeFocused()
      })
    } finally {
      await logger.flush()
    }
  })

  test('dark-theme workspace failure emits diagnostics and preserves an error-state baseline', async ({ page }, testInfo) => {
    const logger = createRegressionLogger(page, testInfo, {
      flow: 'user-menu-workspace-error',
      theme: 'dark',
    })

    try {
      await page.addInitScript(() => {
        localStorage.setItem('boring-ui-theme', 'dark')
      })
      await stubAppBootstrap(page)
      await stubIdentity(page)
      await stubWorkspaces(page, {
        status: 500,
        body: { detail: 'boom' },
      })

      const userMenuButton = await logger.step('navigate to workspace shell', async () => {
        await page.goto('/w/ws-1/')
        return waitForUserMenuButton(page)
      })

      await logger.step('open the menu and surface the workspace error alert', async () => {
        await userMenuButton.click()
        await expect(page.getByRole('menu', { name: 'User menu' }).getByRole('alert')).toHaveText(
          /Failed to load workspaces|boom/i,
        )
      })

      await logger.note('visual-baseline', { snapshot: 'phase1-user-menu-workspaces-error-dark.png' })
      await logger.step('capture the dark-theme workspace-error baseline', async () => {
        await expect(page).toHaveScreenshot('phase1-user-menu-workspaces-error-dark.png')
      })
    } finally {
      await logger.flush()
    }
  })
})
