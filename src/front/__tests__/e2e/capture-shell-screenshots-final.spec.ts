/**
 * Final batch — edge cases and remaining uncovered states.
 */
import { test, type Page, type Route } from '@playwright/test'
import { mkdirSync } from 'fs'
import { resolve } from 'path'

const OUT = resolve(process.cwd(), 'test-results/shell-screenshots')

const json = (v: unknown) => JSON.stringify(v)
const fulfillJson = (route: Route, status: number, body: unknown) =>
  route.fulfill({ status, contentType: 'application/json', body: json(body) })

async function stubBackend(page: Page) {
  await page.route('**/__bui/config', (route) =>
    fulfillJson(route, 200, {
      app: { id: 'boring-ui', name: 'Boring UI', logo: 'B' },
      frontend: {
        branding: { name: 'Boring UI', logo: 'B' },
        data: { backend: 'http' },
        agents: { mode: 'frontend', runtime: 'pi', placement: 'browser' },
        features: { chatCenteredShell: true },
        panels: {},
        mode: { profile: 'frontend' },
      },
      agents: { mode: 'frontend', default: 'pi', available: ['pi'], definitions: [] },
      auth: null,
    }),
  )
  await page.route('**/api/capabilities', (route) =>
    fulfillJson(route, 200, { version: 'test', features: { files: true, git: true, pi: true }, routers: [] }),
  )
  await page.route('**/api/project', (route) => fulfillJson(route, 200, { root: '/' }))
  await page.route('**/api/v1/me', (route) =>
    fulfillJson(route, 200, { user_id: 'ui-review', email: 'reviewer@boring.dev', display_name: 'UI Reviewer' }),
  )
  await page.route('**/api/v1/workspaces', (route) =>
    fulfillJson(route, 200, { workspaces: [{ id: 'ws-1', name: 'Demo Workspace' }] }),
  )
  await page.route('**/api/v1/files/list**', (route) => {
    const url = new URL(route.request().url())
    const p = url.searchParams.get('path') || '.'
    if (p === '.' || p === '/') {
      return fulfillJson(route, 200, { entries: [
        { name: 'src', path: 'src', is_dir: true },
        { name: 'docs', path: 'docs', is_dir: true },
        { name: 'tests', path: 'tests', is_dir: true },
        { name: 'package.json', path: 'package.json', is_dir: false },
        { name: 'README.md', path: 'README.md', is_dir: false },
        { name: 'vite.config.ts', path: 'vite.config.ts', is_dir: false },
      ], path: '.' })
    }
    return fulfillJson(route, 200, { entries: [], path: p })
  })
  await page.route('**/api/v1/files/read**', (route) =>
    fulfillJson(route, 200, { content: '// file content\n', path: '' }),
  )
  await page.route('**/api/v1/files/search**', (route) =>
    fulfillJson(route, 200, { results: [
      { path: 'src/front/App.jsx', line_number: 1, line: 'import React from "react"' },
      { path: 'README.md', line_number: 3, line: '## Getting Started' },
    ] }),
  )
  await page.route('**/api/v1/git/status', (route) =>
    fulfillJson(route, 200, { is_repo: true, files: [] }),
  )
  await page.route('**/api/config**', (route) => fulfillJson(route, 200, {}))
  await page.route('**/api/tree**', (route) =>
    fulfillJson(route, 200, [
      { name: 'src', path: 'src', is_dir: true },
      { name: 'README.md', path: 'README.md', is_dir: false },
    ]),
  )
  await page.route('**/api/**', (route) => {
    if (route.request().method() === 'GET') return fulfillJson(route, 200, {})
    return fulfillJson(route, 200, { success: true })
  })
}

async function waitForShell(page: Page) {
  await page.waitForSelector('[data-testid="chat-centered-workspace"]', { state: 'visible', timeout: 20000 })
  await page.waitForTimeout(500)
}

async function screenshot(page: Page, name: string) {
  await page.waitForTimeout(300)
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: false })
}

test.describe('Final Shell Screenshots', () => {
  test.describe.configure({ timeout: 120_000 })
  test.beforeAll(() => { mkdirSync(OUT, { recursive: true }) })
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await stubBackend(page)
    await page.goto('/?shell=chat-centered', { waitUntil: 'domcontentloaded', timeout: 30000 })
    await page.evaluate(() => { localStorage.clear(); sessionStorage.clear() })
    await page.goto('/?shell=chat-centered', { waitUntil: 'domcontentloaded', timeout: 30000 })
    await waitForShell(page)
  })

  // 28. Long conversation with scroll
  test('28-long-conversation', async ({ page }) => {
    await page.evaluate(() => {
      const msgs: any[] = []
      const topics = [
        ['How do I set up the dev environment?', 'Run `npm install` then `npm run dev`. The backend starts on port 8000 and the frontend on port 5173.'],
        ['What database does it use?', 'PostgreSQL via **Neon** in production, with **Drizzle ORM** for migrations and queries. Locally it uses in-memory storage.'],
        ['How does auth work?', 'JWT session cookies (`boring_session`). HS256-signed, httpOnly, sameSite: lax. In local dev mode, the server auto-creates a session.'],
        ['Can I add a new panel?', "Yes — register it in `registry/panes.jsx` with a component and optional `requiresFeatures` array. The panel system is capability-gated."],
        ['How do I deploy?', 'Run `modal deploy deploy/edge/modal_app.py`. It builds the frontend, bundles it, and deploys to Modal with the server.'],
      ]
      topics.forEach(([q, a], i) => {
        msgs.push({ id: `lc-u${i}`, role: 'user', content: q, parts: [{ type: 'text', text: q }] })
        msgs.push({ id: `lc-a${i}`, role: 'assistant', content: a, parts: [{ type: 'text', text: a }] })
      })
      const state = { activeSessionId: 's-long', sessions: [{ id: 's-long', title: 'Project onboarding', lastModified: Date.now(), status: 'active', draft: '', messages: msgs }] }
      localStorage.setItem('boring-ui:chat-sessions:v1', JSON.stringify(state))
    })
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 })
    await waitForShell(page)
    await screenshot(page, '28-long-conversation')
  })

  // 29. Dark theme long conversation
  test('29-dark-long-conversation', async ({ page }) => {
    await page.evaluate(() => {
      document.documentElement.setAttribute('data-theme', 'dark')
      const msgs: any[] = []
      const topics = [
        ['Explain the layout system', 'The app supports two layouts: **IDE** (DockView panels) and **Chat-centered** (Stage + Wings). Both share the same components from `shared/`.'],
        ['What are the shared components?', 'FileTree, UserMenu, ChatMessage, ToolCallCard, ArtifactCard, CodeEditor, GitDiff — all in `shared/components/`.'],
        ['How does the Surface work?', 'The Surface is the right-side workbench. It uses DockView for tabs/splits and renders EditorPanel for code files. Artifacts open here when the agent edits files.'],
      ]
      topics.forEach(([q, a], i) => {
        msgs.push({ id: `dk-u${i}`, role: 'user', content: q, parts: [{ type: 'text', text: q }] })
        msgs.push({ id: `dk-a${i}`, role: 'assistant', content: a, parts: [{ type: 'text', text: a }] })
      })
      const state = { activeSessionId: 's-dk-long', sessions: [{ id: 's-dk-long', title: 'Architecture deep dive', lastModified: Date.now(), status: 'active', draft: '', messages: msgs }] }
      localStorage.setItem('boring-ui:chat-sessions:v1', JSON.stringify(state))
    })
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 })
    await waitForShell(page)
    await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'))
    await page.waitForTimeout(300)
    await screenshot(page, '29-dark-long-conversation')
  })

  // 30. Mixed tool types in one message (read + bash + grep + write)
  test('30-mixed-tools', async ({ page }) => {
    await page.evaluate(() => {
      const state = { activeSessionId: 's-mix', sessions: [{ id: 's-mix', title: 'Code review', lastModified: Date.now(), status: 'active', draft: '', messages: [
        { id: 'mx1', role: 'user', content: 'Review the auth module for security issues', parts: [{ type: 'text', text: 'Review the auth module for security issues' }] },
        { id: 'mx2', role: 'assistant', content: '', parts: [
          { type: 'text', text: "I'll review the auth module. Let me examine the key files." },
          { type: 'tool-result', toolCallId: 'mx-t1', toolName: 'read_file', input: { path: 'src/server/auth/session.ts' }, output: 'export async function createSessionCookie(...)' },
          { type: 'tool-result', toolCallId: 'mx-t2', toolName: 'read_file', input: { path: 'src/server/auth/middleware.ts' }, output: 'export function createAuthHook(app) { ... }' },
          { type: 'tool-result', toolCallId: 'mx-t3', toolName: 'grep', input: { pattern: 'secret|password|token', path: 'src/server/' }, output: 'src/server/auth/session.ts:28:  const secretKey = new TextEncoder().encode(secret)\nsrc/server/config.ts:314:    sessionSecret,' },
          { type: 'tool-result', toolCallId: 'mx-t4', toolName: 'bash', input: { command: 'grep -r "eval\\|exec" src/server/ | wc -l' }, output: '0' },
          { type: 'text', text: "**Security review results:**\n\n- No `eval()` or `exec()` calls found\n- Session secrets are properly encoded via `TextEncoder`\n- Cookies use `httpOnly` + `sameSite: lax` flags\n- JWT validation uses `jose` library with clock skew tolerance\n\nNo critical issues found. The auth module follows security best practices." },
        ]},
      ]}] }
      localStorage.setItem('boring-ui:chat-sessions:v1', JSON.stringify(state))
    })
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 })
    await waitForShell(page)
    await screenshot(page, '30-mixed-tools')
  })

  // 31. Dark theme error state
  test('31-dark-error', async ({ page }) => {
    await page.evaluate(() => {
      document.documentElement.setAttribute('data-theme', 'dark')
      const state = { activeSessionId: 's-dk-err', sessions: [{ id: 's-dk-err', title: 'Error in dark', lastModified: Date.now(), status: 'active', draft: '', messages: [
        { id: 'de1', role: 'user', content: 'Run the failing test', parts: [{ type: 'text', text: 'Run the failing test' }] },
        { id: 'de2', role: 'assistant', content: '', parts: [
          { type: 'tool-result', toolCallId: 'de-t1', toolName: 'bash', input: { command: 'npm run test -- --filter=auth' }, output: '', status: 'error', isError: true },
          { type: 'tool-error', toolCallId: 'de-t1', toolName: 'bash', error: 'FAIL src/server/auth/session.test.ts\n  ● createSessionCookie › throws on empty secret\n    Expected: SessionError\n    Received: undefined' },
          { type: 'text', text: "The test `createSessionCookie › throws on empty secret` is failing. The function doesn't validate the secret parameter before signing.\n\n**Fix:** Add a guard at the top of `createSessionCookie`:\n```ts\nif (!secret) throw new SessionError('Secret is required')\n```" },
        ]},
      ]}] }
      localStorage.setItem('boring-ui:chat-sessions:v1', JSON.stringify(state))
    })
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 })
    await waitForShell(page)
    await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'))
    await page.waitForTimeout(300)
    await screenshot(page, '31-dark-error')
  })

  // 32. Dark theme with code block
  test('32-dark-code-block', async ({ page }) => {
    await page.evaluate(() => {
      document.documentElement.setAttribute('data-theme', 'dark')
      const state = { activeSessionId: 's-dk-code', sessions: [{ id: 's-dk-code', title: 'Code in dark', lastModified: Date.now(), status: 'active', draft: '', messages: [
        { id: 'dc1', role: 'user', content: 'Show me a middleware example', parts: [{ type: 'text', text: 'Show me a middleware example' }] },
        { id: 'dc2', role: 'assistant', content: '', parts: [
          { type: 'text', text: "Here's a rate limiting middleware:\n\n```typescript\nconst rateLimit = new Map<string, number[]>()\n\nexport function rateLimitHook(limit = 100, windowMs = 60000) {\n  return async (request: FastifyRequest, reply: FastifyReply) => {\n    const key = request.ip\n    const now = Date.now()\n    const hits = (rateLimit.get(key) || []).filter(t => t > now - windowMs)\n    \n    if (hits.length >= limit) {\n      return reply.code(429).send({\n        error: 'rate_limited',\n        retryAfter: Math.ceil((hits[0] + windowMs - now) / 1000)\n      })\n    }\n    \n    hits.push(now)\n    rateLimit.set(key, hits)\n  }\n}\n```\n\nUsage:\n```typescript\napp.addHook('onRequest', rateLimitHook(100, 60000))\n```" },
        ]},
      ]}] }
      localStorage.setItem('boring-ui:chat-sessions:v1', JSON.stringify(state))
    })
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 })
    await waitForShell(page)
    await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'))
    await page.waitForTimeout(300)
    await screenshot(page, '32-dark-code-block')
  })

  // 33. Surface search with results (light)
  test('33-search-with-results', async ({ page }) => {
    await page.click('[data-testid="nav-rail-surface"]')
    await page.waitForSelector('[data-testid="surface-shell"]', { state: 'visible', timeout: 5000 })
    const searchTab = page.locator('[aria-label="Search"]').first()
    await searchTab.click()
    const searchInput = page.locator('[aria-label="Search files and data catalog"]').first()
    await searchInput.fill('import')
    await page.waitForTimeout(800)
    await screenshot(page, '33-search-with-results')
  })

  // 34. Wide viewport (ultrawide)
  test('34-ultrawide', async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 })
    await page.evaluate(() => {
      const state = { activeSessionId: 's-wide', sessions: [{ id: 's-wide', title: 'Ultrawide view', lastModified: Date.now(), status: 'active', draft: '', messages: [
        { id: 'w1', role: 'user', content: 'How is the project structured?', parts: [{ type: 'text', text: 'How is the project structured?' }] },
        { id: 'w2', role: 'assistant', content: '', parts: [
          { type: 'text', text: "The project follows a **shared building blocks + layout modes** architecture:\n\n- `layouts/chat/` — Chat-centered Stage + Wings layout\n- `layouts/ide/` — (future) IDE DockView layout\n- `shared/` — Cross-layout shared layer (design system, components, providers, hooks)\n\nBoth layouts reuse the same FileTree, ChatMessage, UserMenu, CodeEditor, and design tokens." },
        ]},
      ]}] }
      localStorage.setItem('boring-ui:chat-sessions:v1', JSON.stringify(state))
    })
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 })
    await waitForShell(page)
    await screenshot(page, '34-ultrawide')
  })

  // 35. Dark theme with reasoning block
  test('35-dark-reasoning', async ({ page }) => {
    await page.evaluate(() => {
      document.documentElement.setAttribute('data-theme', 'dark')
      const state = { activeSessionId: 's-dk-reason', sessions: [{ id: 's-dk-reason', title: 'Dark reasoning', lastModified: Date.now(), status: 'active', draft: '', messages: [
        { id: 'dr1', role: 'user', content: 'Should we use WebSockets or SSE for streaming?', parts: [{ type: 'text', text: 'Should we use WebSockets or SSE for streaming?' }] },
        { id: 'dr2', role: 'assistant', content: '', parts: [
          { type: 'reasoning', reasoning: "Let me think about this. WebSockets provide full-duplex communication but add complexity (connection management, reconnection logic, CORS). SSE is simpler, works over HTTP, auto-reconnects, and is sufficient for server→client streaming which is the primary use case for chat responses. The app already uses SSE for the AI SDK transport." },
          { type: 'text', text: "**SSE (Server-Sent Events)** is the better choice here:\n\n- **Simpler** — works over standard HTTP, no upgrade handshake\n- **Auto-reconnect** — built into the EventSource API\n- **Sufficient** — chat streaming is server→client only\n- **Already in use** — the AI SDK transport uses SSE\n\nWebSockets would only be needed if you add real-time collaboration (multiple cursors, live editing)." },
        ]},
      ]}] }
      localStorage.setItem('boring-ui:chat-sessions:v1', JSON.stringify(state))
    })
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 })
    await waitForShell(page)
    await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'))
    await page.waitForTimeout(300)
    await screenshot(page, '35-dark-reasoning')
  })
})
