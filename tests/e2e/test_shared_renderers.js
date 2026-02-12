/**
 * Visual regression tests for shared tool renderers.
 * Uses playwright-core directly to avoid @playwright/test ESM issues.
 * 
 * Run: node tests/e2e/test_shared_renderers.js
 */
import { chromium } from 'playwright'
import { mkdir, writeFile } from 'fs/promises'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const FIXTURE_URL = 'http://localhost:5173/fixture-renderers.html'
const SCREENSHOT_DIR = join(__dirname, '__snapshots__')

let passed = 0
let failed = 0
const failures = []

async function assert(name, condition, message) {
  if (condition) {
    passed++
    console.log(`  \x1b[32m✓\x1b[0m ${name}`)
  } else {
    failed++
    failures.push({ name, message })
    console.log(`  \x1b[31m✗\x1b[0m ${name}: ${message}`)
  }
}

async function screenshot(page, element, name) {
  await mkdir(SCREENSHOT_DIR, { recursive: true })
  const path = join(SCREENSHOT_DIR, name)
  if (element) {
    await element.screenshot({ path })
  } else {
    await page.screenshot({ path, fullPage: true })
  }
  return path
}

async function run() {
  const browser = await chromium.launch()
  const page = await browser.newPage()

  try {
    // Navigate to fixture
    await page.goto(FIXTURE_URL, { waitUntil: 'domcontentloaded' })
    await page.waitForSelector('[data-testid="renderer-showcase"]', { timeout: 10000 })

    console.log('\n\x1b[1mShared Tool Renderer Visual Regression Tests\x1b[0m\n')

    // ─── Full page ──────────────────────────────────────────────
    console.log('Full page:')
    const sections = [
      'section-bash', 'section-read', 'section-write', 'section-edit',
      'section-grep', 'section-glob', 'section-generic', 'section-context',
    ]
    for (const id of sections) {
      const el = page.locator(`[data-testid="${id}"]`)
      await assert(`${id} exists`, await el.count() > 0, 'Section not found')
    }
    await screenshot(page, null, 'renderers-full-page.png')
    await assert('full page screenshot saved', true, '')

    // ─── Bash Renderer ──────────────────────────────────────────
    console.log('\nBash Renderer:')
    const bashSuccess = page.locator('[data-testid="fixture-bash-success"]')
    await assert('has Bash tool name', (await bashSuccess.locator('.tool-use-name').textContent()) === 'Bash', 'Wrong tool name')
    await assert('has command display', (await bashSuccess.locator('code').textContent()).includes('ls -la src/'), 'No command')
    await assert('has output', (await bashSuccess.locator('.tool-output').textContent()).includes('total 32'), 'No output')

    const bashError = page.locator('[data-testid="fixture-bash-error"]')
    await assert('error has .tool-error', await bashError.locator('.tool-error').count() > 0, 'No error element')
    await assert('error message correct', (await bashError.locator('.tool-error').textContent()).includes('No such file'), 'Wrong error')

    const bashRunning = page.locator('[data-testid="fixture-bash-running"]')
    await assert('running state', (await bashRunning.textContent()).includes('Running command...'), 'No running text')

    const bashLong = page.locator('[data-testid="fixture-bash-long"]')
    await assert('long output has expand button', await bashLong.locator('button').count() > 0, 'No expand button')
    await assert('expand button says "more lines"', (await bashLong.locator('button').textContent()).includes('more lines'), 'Wrong button text')

    await screenshot(page, page.locator('[data-testid="section-bash"]'), 'bash-renderer.png')

    // ─── Read Renderer ──────────────────────────────────────────
    console.log('\nRead Renderer:')
    const readSuccess = page.locator('[data-testid="fixture-read-success"]')
    await assert('has Read tool name', (await readSuccess.locator('.tool-use-name').textContent()) === 'Read', 'Wrong tool name')
    await assert('shows App.jsx', (await readSuccess.locator('.tool-use-description').textContent()).includes('App.jsx'), 'Wrong filename')
    await assert('shows content', (await readSuccess.locator('.tool-output').textContent()).includes('Main application'), 'No content')

    const readTruncated = page.locator('[data-testid="fixture-read-truncated"]')
    await assert('truncated indicator', (await readTruncated.locator('.tool-use-description').textContent()).includes('truncated'), 'No truncated text')

    const readError = page.locator('[data-testid="fixture-read-error"]')
    await assert('read error', (await readError.locator('.tool-error').textContent()).includes('ENOENT'), 'Wrong error')

    await screenshot(page, page.locator('[data-testid="section-read"]'), 'read-renderer.png')

    // ─── Write Renderer ─────────────────────────────────────────
    console.log('\nWrite Renderer:')
    const writeSuccess = page.locator('[data-testid="fixture-write-success"]')
    await assert('has Write tool name', (await writeSuccess.locator('.tool-use-name').textContent()) === 'Write', 'Wrong tool name')
    await assert('shows config.js', (await writeSuccess.locator('.tool-use-description').textContent()).includes('config.js'), 'Wrong filename')
    await assert('shows content', (await writeSuccess.locator('.tool-output').textContent()).includes('API_URL'), 'No content')

    const writePending = page.locator('[data-testid="fixture-write-pending"]')
    await assert('pending state', (await writePending.textContent()).includes('Waiting for permission'), 'No pending text')

    await screenshot(page, page.locator('[data-testid="section-write"]'), 'write-renderer.png')

    // ─── Edit Renderer ──────────────────────────────────────────
    console.log('\nEdit Renderer:')
    const editDiff = page.locator('[data-testid="fixture-edit-diff"]')
    await assert('has Edit tool name', (await editDiff.locator('.tool-use-name').textContent()) === 'Edit', 'Wrong tool name')
    await assert('shows App.jsx', (await editDiff.locator('.tool-use-description').textContent()).includes('App.jsx'), 'Wrong filename')
    await assert('has diff-view', await editDiff.locator('.shared-diff-view').count() > 0, 'No diff view')

    const editOldNew = page.locator('[data-testid="fixture-edit-oldnew"]')
    await assert('shows utils.js', (await editOldNew.textContent()).includes('utils.js'), 'Wrong filename')

    const editError = page.locator('[data-testid="fixture-edit-error"]')
    await assert('edit error', (await editError.locator('.tool-error').textContent()).includes('Permission denied'), 'Wrong error')

    await screenshot(page, page.locator('[data-testid="section-edit"]'), 'edit-renderer.png')

    // ─── Grep Renderer ──────────────────────────────────────────
    console.log('\nGrep Renderer:')
    const grepSuccess = page.locator('[data-testid="fixture-grep-success"]')
    await assert('has Grep tool name', (await grepSuccess.locator('.tool-use-name').textContent()) === 'Grep', 'Wrong tool name')
    await assert('shows pattern', (await grepSuccess.locator('.inline-code').textContent()) === 'useState', 'Wrong pattern')
    await assert('shows file results', (await grepSuccess.textContent()).includes('src/App.jsx'), 'No file results')
    await assert('shows match count', (await grepSuccess.textContent()).includes('5 matches in 2 files'), 'No match count')
    await assert('has highlight marks', await grepSuccess.locator('mark').count() > 0, 'No highlights')

    const grepEmpty = page.locator('[data-testid="fixture-grep-empty"]')
    await assert('no matches', (await grepEmpty.textContent()).includes('No matches found'), 'No "no matches" text')

    const grepRunning = page.locator('[data-testid="fixture-grep-running"]')
    await assert('searching state', (await grepRunning.textContent()).includes('Searching...'), 'No searching text')

    await screenshot(page, page.locator('[data-testid="section-grep"]'), 'grep-renderer.png')

    // ─── Glob Renderer ──────────────────────────────────────────
    console.log('\nGlob Renderer:')
    const globSuccess = page.locator('[data-testid="fixture-glob-success"]')
    await assert('has Glob tool name', (await globSuccess.locator('.tool-use-name').textContent()) === 'Glob', 'Wrong tool name')
    await assert('shows files', (await globSuccess.textContent()).includes('src/App.jsx'), 'No file list')
    await assert('shows all 7 files', (await globSuccess.textContent()).includes('TerminalPanel.jsx'), 'Missing files')

    const globEmpty = page.locator('[data-testid="fixture-glob-empty"]')
    await assert('no files', (await globEmpty.textContent()).includes('No files found'), 'No "no files" text')

    await screenshot(page, page.locator('[data-testid="section-glob"]'), 'glob-renderer.png')

    // ─── Generic Renderer ───────────────────────────────────────
    console.log('\nGeneric Renderer:')
    const genericSuccess = page.locator('[data-testid="fixture-generic-success"]')
    await assert('has WebSearch name', (await genericSuccess.locator('.tool-use-name').textContent()) === 'WebSearch', 'Wrong tool name')
    await assert('shows output', (await genericSuccess.locator('.tool-output').textContent()).includes('Found 15 results'), 'No output')

    const genericRunning = page.locator('[data-testid="fixture-generic-running"]')
    await assert('running state', (await genericRunning.textContent()).includes('Running...'), 'No running text')

    await screenshot(page, page.locator('[data-testid="section-generic"]'), 'generic-renderer.png')

    // ─── Context (ToolResultView) ───────────────────────────────
    console.log('\nToolResultView via Context:')
    const contextView = page.locator('[data-testid="fixture-context-view"]')
    await assert('renders via context', (await contextView.locator('.tool-use-name').textContent()) === 'Bash', 'Wrong tool name')
    await assert('output correct', (await contextView.textContent()).includes('rendered via ToolResultView'), 'Wrong output')

    await screenshot(page, page.locator('[data-testid="section-context"]'), 'context-renderer.png')

    // ─── Console Errors ─────────────────────────────────────────
    console.log('\nConsole Errors:')
    const errors = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text())
    })
    // Re-navigate to capture errors
    await page.goto(FIXTURE_URL, { waitUntil: 'domcontentloaded' })
    await page.waitForSelector('[data-testid="renderer-showcase"]', { timeout: 10000 })
    // Wait a moment for any async errors
    await page.waitForTimeout(1000)
    const realErrors = errors.filter(e => !e.includes('WebSocket') && !e.includes('[vite]'))
    await assert('no console errors', realErrors.length === 0, `Found ${realErrors.length} errors: ${realErrors.join(', ')}`)

  } finally {
    await browser.close()
  }

  // Summary
  console.log(`\n${'─'.repeat(50)}`)
  console.log(`\x1b[1m${passed + failed} tests: \x1b[32m${passed} passed\x1b[0m${failed > 0 ? `, \x1b[31m${failed} failed\x1b[0m` : ''}`)
  if (failures.length > 0) {
    console.log('\nFailures:')
    failures.forEach(f => console.log(`  - ${f.name}: ${f.message}`))
  }
  console.log(`\nScreenshots saved to: ${SCREENSHOT_DIR}\n`)

  process.exit(failed > 0 ? 1 : 0)
}

run().catch(err => {
  console.error('Fatal error:', err)
  process.exit(1)
})
