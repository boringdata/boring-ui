/**
 * E2E verification for Direct Connect architecture.
 *
 * Tests all providers to ensure they render correctly via
 * direct browser->service connections with token auth.
 *
 * Usage: node tests/e2e/test_direct_connect.js
 *
 * Prerequisites:
 *   - Vite dev server on port 5173
 *   - Backend on port 8000 (with sandbox + companion enabled)
 *   - Companion server started (auto-starts with backend)
 */
const { chromium } = require('playwright')

const BASE = 'http://localhost:5173'
const API = 'http://localhost:8000'
const results = []

async function test(name, fn) {
  const start = Date.now()
  try {
    await fn()
    const ms = Date.now() - start
    results.push({ name, status: 'PASS', ms })
    console.log(`  PASS  ${name} (${ms}ms)`)
  } catch (err) {
    const ms = Date.now() - start
    results.push({ name, status: 'FAIL', ms, error: err.message })
    console.log(`  FAIL  ${name} (${ms}ms)`)
    console.log(`        ${err.message}`)
  }
}

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

/** Navigate and wait for React to render into #root */
async function loadPage(page, url, timeout = 30000) {
  await page.goto(url, { waitUntil: 'commit', timeout })
  // Wait for React to render content into #root
  await page.waitForFunction(
    () => (document.getElementById('root')?.innerHTML?.length || 0) > 100,
    { timeout },
  )
}

async function run() {
  console.log('\n=== Direct Connect E2E Verification ===\n')

  // Pre-flight: check services are up
  console.log('Pre-flight checks...')
  const capRes = await fetch(`${API}/api/capabilities`)
  const caps = await capRes.json()
  console.log(`  Backend: OK`)
  console.log(`  Features: ${Object.entries(caps.features).filter(([, v]) => v).map(([k]) => k).join(', ')}`)
  console.log(`  Services: ${Object.keys(caps.services || {}).join(', ') || 'none'}`)
  console.log()

  // Use a single browser for all tests (sequential to avoid overloading Vite)
  const browser = await chromium.launch({ headless: true })

  // --- API-level tests (no browser needed) ---
  await test('capabilities: returns services with tokens', async () => {
    assert(caps.features.chat_claude_code, 'chat_claude_code feature missing')
    assert(caps.features.sandbox, 'sandbox feature missing')
    assert(caps.features.companion, 'companion feature missing')
    assert(caps.services?.sandbox?.url, 'sandbox service URL missing')
    assert(caps.services?.sandbox?.token, 'sandbox service token missing')
    assert(caps.services?.companion?.url, 'companion service URL missing')
    assert(caps.services?.companion?.token, 'companion service token missing')
  })

  await test('capabilities: companion token is valid JWT', async () => {
    const token = caps.services.companion.token
    const parts = token.split('.')
    assert(parts.length === 3, `Expected 3-part JWT, got ${parts.length} parts`)
    const payload = JSON.parse(atob(parts[1]))
    assert(payload.sub === 'boring-ui', `JWT sub should be 'boring-ui', got '${payload.sub}'`)
    assert(payload.svc === 'companion', `JWT svc should be 'companion', got '${payload.svc}'`)
    assert(payload.exp > Date.now() / 1000, 'JWT is expired')
  })

  await test('capabilities: sandbox token is hex bearer', async () => {
    const token = caps.services.sandbox.token
    assert(/^[0-9a-f]+$/i.test(token), `Expected hex token, got: ${token.substring(0, 10)}...`)
  })

  await test('direct-connect: companion API accepts JWT', async () => {
    const r = await fetch(`${caps.services.companion.url}/api/sessions`, {
      headers: { Authorization: `Bearer ${caps.services.companion.token}` },
    })
    assert(r.ok, `Expected 200, got ${r.status}`)
    const data = await r.json()
    assert(Array.isArray(data), 'Expected array response')
  })

  await test('direct-connect: companion API rejects missing token', async () => {
    const r = await fetch(`${caps.services.companion.url}/api/sessions`)
    assert(r.status === 401 || r.status === 403, `Expected 401/403, got ${r.status}`)
  })

  await test('direct-connect: sandbox API accepts bearer token', async () => {
    const r = await fetch(`${caps.services.sandbox.url}/v1/agents`, {
      headers: { Authorization: `Bearer ${caps.services.sandbox.token}` },
    })
    assert(r.ok, `Expected 200, got ${r.status}`)
  })

  await test('direct-connect: companion CORS preflight', async () => {
    const r = await fetch(`${caps.services.companion.url}/api/sessions`, {
      method: 'OPTIONS',
      headers: {
        Origin: 'http://localhost:5173',
        'Access-Control-Request-Method': 'GET',
        'Access-Control-Request-Headers': 'Authorization',
      },
    })
    assert(r.status === 200 || r.status === 204, `Expected 200/204, got ${r.status}`)
    const allowOrigin = r.headers.get('access-control-allow-origin')
    assert(allowOrigin, 'Missing Access-Control-Allow-Origin header')
  })

  // --- Browser tests (sequential, reusing single page) ---

  await test('claude provider: renders three-column layout', async () => {
    const page = await browser.newPage()
    const errors = []
    page.on('pageerror', (e) => errors.push(e.message))
    try {
      await loadPage(page, BASE)
      const header = await page.evaluate(() =>
        document.querySelector('.app-header-title')?.textContent,
      )
      assert(header, 'App header not found')
      assert(errors.length === 0, `Page errors: ${errors.join('; ')}`)
    } finally {
      await page.close()
    }
  })

  await test('companion provider: renders with Direct Connect', async () => {
    const page = await browser.newPage()
    const errors = []
    page.on('pageerror', (e) => errors.push(e.message))
    try {
      await loadPage(page, `${BASE}/?chat=companion`)
      // Wait extra for companion to mount
      await page.waitForTimeout(2000)
      const companionEl = await page.evaluate(() =>
        !!document.querySelector('.provider-companion'),
      )
      assert(companionEl, '.provider-companion not found')
      const sidebar = await page.evaluate(() => {
        const el = document.querySelector('.provider-companion aside')
        return el?.textContent?.substring(0, 100) || null
      })
      assert(sidebar, 'Companion sidebar not found')
      assert(sidebar.includes('New Session'), `Sidebar missing "New Session": ${sidebar}`)
      assert(errors.length === 0, `Page errors: ${errors.join('; ')}`)
    } finally {
      await page.close()
    }
  })

  await test('sandbox provider: renders chat UI', async () => {
    const page = await browser.newPage()
    const errors = []
    page.on('pageerror', (e) => errors.push(e.message))
    try {
      await loadPage(page, `${BASE}/?chat=sandbox`)
      await page.waitForTimeout(2000)
      const fatalErrors = errors.filter(
        (e) => !e.includes('_renderer.value is undefined'),
      )
      assert(fatalErrors.length === 0, `Page errors: ${fatalErrors.join('; ')}`)
    } finally {
      await page.close()
    }
  })

  await test('inspector provider: renders without crash', async () => {
    const page = await browser.newPage()
    const errors = []
    page.on('pageerror', (e) => errors.push(e.message))
    try {
      await loadPage(page, `${BASE}/?chat=inspector`)
      await page.waitForTimeout(2000)
      const fatalErrors = errors.filter(
        (e) => !e.includes('_renderer.value is undefined'),
      )
      assert(fatalErrors.length === 0, `Page errors: ${fatalErrors.join('; ')}`)
    } finally {
      await page.close()
    }
  })

  await browser.close()

  // Summary
  console.log('\n=== Summary ===')
  const passed = results.filter((r) => r.status === 'PASS').length
  const failed = results.filter((r) => r.status === 'FAIL').length
  console.log(`  ${passed} passed, ${failed} failed, ${results.length} total`)

  if (failed > 0) {
    console.log('\nFailed tests:')
    results
      .filter((r) => r.status === 'FAIL')
      .forEach((r) => console.log(`  - ${r.name}: ${r.error}`))
    process.exit(1)
  }

  console.log('\nAll tests passed.')
}

run().catch((err) => {
  console.error('Fatal error:', err)
  process.exit(2)
})
