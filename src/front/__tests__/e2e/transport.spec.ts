import { expect, test } from '@playwright/test'

test.describe('Canonical Transport Regression', () => {
  test('user menu bootstrap + logout use canonical control-plane routes', async ({ page }) => {
    const apiPaths = new Set<string>()

    page.on('request', (request) => {
      const url = new URL(request.url())
      if (url.pathname.startsWith('/api/') || url.pathname === '/auth/logout') {
        apiPaths.add(url.pathname)
      }
    })

    await page.route('**/auth/logout', (route) => {
      route.fulfill({
        status: 204,
        body: '',
      })
    })

    await page.goto('/')
    await page.waitForSelector('[aria-label="User menu"]', { timeout: 15000 })

    await expect.poll(() => apiPaths.has('/api/v1/me')).toBe(true)
    await expect.poll(() => apiPaths.has('/api/v1/workspaces')).toBe(true)
    expect(Array.from(apiPaths)).not.toContain('/api/me')
    expect(Array.from(apiPaths)).not.toContain('/api/workspaces')

    const logoutRequest = page.waitForRequest(
      (request) => new URL(request.url()).pathname === '/auth/logout',
    )
    await page.getByRole('button', { name: 'User menu' }).click()
    await page.getByRole('menuitem', { name: 'Logout' }).click()
    await logoutRequest
  })
})
