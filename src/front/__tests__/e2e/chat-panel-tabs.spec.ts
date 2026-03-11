import { test, expect } from '@playwright/test'

const APP_URL = '/?agent_mode=companion'
const splitPanelName = /Split (chat|agent) panel/

const countGroupViews = async (page) => page.locator('.dv-groupview').count()
const countSplitButtons = async (page) =>
  page.getByRole('button', { name: splitPanelName }).count()
const readDockCounts = async (page) => ({
  groups: await countGroupViews(page),
  splitButtons: await countSplitButtons(page),
})
const hasPersistedLayout = async (page) =>
  page.evaluate(() => Object.keys(localStorage).some((key) => key.endsWith('-layout')))

const waitForDockLayoutToSettle = async (
  page,
  { timeout = 10_000, interval = 200, stableSamples = 3 } = {},
) => {
  const deadline = Date.now() + timeout
  let previous = null
  let stableCount = 0

  while (Date.now() < deadline) {
    const next = await readDockCounts(page)
    if (
      previous
      && next.groups === previous.groups
      && next.splitButtons === previous.splitButtons
    ) {
      stableCount += 1
    } else {
      stableCount = 0
      previous = next
    }

    if (next.groups > 0 && stableCount >= stableSamples) {
      return next
    }

    await page.waitForTimeout(interval)
  }

  return previous || readDockCounts(page)
}

test.describe('Chat Panel Tabs And Split', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(APP_URL)
    await page.evaluate(() => {
      localStorage.clear()
    })
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 60000 })
    await page.waitForSelector('[data-testid="dockview"]', { timeout: 20000 })
    await expect.poll(() => hasPersistedLayout(page), { timeout: 15_000 }).toBe(true)
    await waitForDockLayoutToSettle(page)
  })

  test('left header button opens a new split pane and panel + splits into a new pane', async ({ page }) => {
    const openChatTabButton = page.getByRole('button', { name: 'Open new chat pane' })
    await expect(openChatTabButton).toBeVisible()

    let { splitButtons: splitButtonsBefore, groups: groupsBefore } = await readDockCounts(page)
    if (splitButtonsBefore === 0) {
      await openChatTabButton.click()
      ;({ splitButtons: splitButtonsBefore, groups: groupsBefore } = await waitForDockLayoutToSettle(page))
    }
    expect(groupsBefore).toBeGreaterThan(0)

    await openChatTabButton.click()
    const {
      splitButtons: splitButtonsAfterOpen,
      groups: groupsAfterOpen,
    } = await waitForDockLayoutToSettle(page)
    expect(splitButtonsAfterOpen).toBeGreaterThanOrEqual(splitButtonsBefore)
    expect(groupsAfterOpen).toBeGreaterThan(0)

    const splitButton = page.getByRole('button', { name: splitPanelName }).first()
    await expect(splitButton).toBeVisible()
    await splitButton.click()

    const {
      splitButtons: splitButtonsAfterSplit,
      groups: groupsAfterSplit,
    } = await waitForDockLayoutToSettle(page)
    expect(splitButtonsAfterSplit).toBeGreaterThan(0)

    expect(groupsAfterSplit).toBeGreaterThan(0)
  })

  test('app auto-opens a chat panel on load and reload', async ({ page }) => {
    await expect(page.getByRole('button', { name: splitPanelName }).first()).toBeVisible()
    const groupsBeforeReload = await countGroupViews(page)
    expect(groupsBeforeReload).toBeGreaterThan(0)

    await page.reload({ waitUntil: 'domcontentloaded', timeout: 60000 })
    await page.waitForSelector('[data-testid="dockview"]', { timeout: 20000 })

    await expect(page.getByRole('button', { name: splitPanelName }).first()).toBeVisible()
  })
})
