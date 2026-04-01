/**
 * Shell UI Screenshot Capture
 *
 * Captures the chat-centered layout in 15 key states for visual review.
 * Run: npx playwright test scripts/capture-shell-screenshots.ts --reporter=list
 */
import { test, expect, type Page, type Route } from '@playwright/test'
import { mkdirSync } from 'fs'
import { resolve } from 'path'

const OUT = resolve(process.cwd(), 'test-results/shell-screenshots')
const BASE = 'http://127.0.0.1:4173'

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
    fulfillJson(route, 200, {
      version: 'test', features: { files: true, git: true, pi: true }, routers: [],
    }),
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
      return fulfillJson(route, 200, {
        entries: [
          { name: 'src', path: 'src', is_dir: true },
          { name: 'docs', path: 'docs', is_dir: true },
          { name: 'tests', path: 'tests', is_dir: true },
          { name: 'package.json', path: 'package.json', is_dir: false },
          { name: 'README.md', path: 'README.md', is_dir: false },
          { name: 'tsconfig.json', path: 'tsconfig.json', is_dir: false },
          { name: 'vite.config.ts', path: 'vite.config.ts', is_dir: false },
        ],
        path: '.',
      })
    }
    if (p === 'src') {
      return fulfillJson(route, 200, {
        entries: [
          { name: 'front', path: 'src/front', is_dir: true },
          { name: 'server', path: 'src/server', is_dir: true },
          { name: 'shared', path: 'src/shared', is_dir: true },
        ],
        path: 'src',
      })
    }
    return fulfillJson(route, 200, { entries: [], path: p })
  })
  await page.route('**/api/v1/files/read**', (route) => {
    const url = new URL(route.request().url())
    const p = url.searchParams.get('path') || ''
    if (p.endsWith('.md')) {
      return fulfillJson(route, 200, { content: '# Welcome\n\nThis is a demo file for UI review.\n\n## Features\n\n- Chat-centered layout\n- Surface workbench\n- Session management\n', path: p })
    }
    if (p.endsWith('.json')) {
      return fulfillJson(route, 200, { content: '{\n  "name": "boring-ui",\n  "version": "0.1.0",\n  "type": "module"\n}\n', path: p })
    }
    return fulfillJson(route, 200, { content: '// File content\nconsole.log("hello")\n', path: p })
  })
  await page.route('**/api/v1/files/search**', (route) =>
    fulfillJson(route, 200, {
      results: [
        { path: 'src/front/App.jsx', line_number: 1, line: 'import React from "react"' },
        { path: 'src/server/index.ts', line_number: 5, line: 'const app = createApp()' },
        { path: 'README.md', line_number: 3, line: '## Getting Started' },
      ],
    }),
  )
  await page.route('**/api/v1/git/status', (route) =>
    fulfillJson(route, 200, { is_repo: true, files: [] }),
  )
  await page.route('**/api/config**', (route) => fulfillJson(route, 200, {}))
  await page.route('**/api/tree**', (route) =>
    fulfillJson(route, 200, [
      { name: 'src', path: 'src', is_dir: true },
      { name: 'package.json', path: 'package.json', is_dir: false },
      { name: 'README.md', path: 'README.md', is_dir: false },
    ]),
  )
  // Catch-all for other API calls
  await page.route('**/api/**', (route) => {
    if (route.request().method() === 'GET') return fulfillJson(route, 200, {})
    return fulfillJson(route, 200, { success: true })
  })
}

async function waitForShell(page: Page) {
  await page.waitForSelector('[data-testid="chat-centered-workspace"]', { state: 'visible', timeout: 20000 })
  // Let animations settle
  await page.waitForTimeout(500)
}

async function screenshot(page: Page, name: string) {
  await page.waitForTimeout(300) // settle
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: false })
}

test.describe('Shell UI Screenshots', () => {
  test.describe.configure({ timeout: 120_000 })

  test.beforeAll(() => {
    mkdirSync(OUT, { recursive: true })
  })

  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await stubBackend(page)
    await page.goto('/?shell=chat-centered', { waitUntil: 'domcontentloaded', timeout: 30000 })
    await page.evaluate(() => { localStorage.clear(); sessionStorage.clear() })
    await page.goto('/?shell=chat-centered', { waitUntil: 'domcontentloaded', timeout: 30000 })
    await waitForShell(page)
  })

  // 1. Default state — chat empty, no wings open
  test('01-default-empty-state', async ({ page }) => {
    await screenshot(page, '01-default-empty-state')
  })

  // 2. Composer focused with text typed
  test('02-composer-with-input', async ({ page }) => {
    const input = page.locator('.vc-composer-input')
    await input.click()
    await input.fill('List all files in the src directory and show me the project structure')
    await page.waitForTimeout(200)
    await screenshot(page, '02-composer-with-input')
  })

  // 3. Sessions drawer open
  test('03-sessions-drawer-open', async ({ page }) => {
    await page.click('[data-testid="nav-rail-history"]')
    await page.waitForSelector('[data-testid="browse-drawer"]', { state: 'visible', timeout: 5000 })
    await screenshot(page, '03-sessions-drawer-open')
  })

  // 4. Surface open (empty, no artifacts)
  test('04-surface-open-empty', async ({ page }) => {
    await page.click('[data-testid="nav-rail-surface"]')
    await page.waitForSelector('[data-testid="surface-shell"]', { state: 'visible', timeout: 5000 })
    await screenshot(page, '04-surface-open-empty')
  })

  // 5. Surface with file tree expanded
  test('05-surface-file-tree', async ({ page }) => {
    await page.click('[data-testid="nav-rail-surface"]')
    await page.waitForSelector('[data-testid="surface-shell"]', { state: 'visible', timeout: 5000 })
    // Wait for file tree to load
    await page.waitForSelector('.file-tree, .filetree-body, [class*="filetree"]', { state: 'visible', timeout: 10000 }).catch(() => {})
    await page.waitForTimeout(500)
    await screenshot(page, '05-surface-file-tree')
  })

  // 6. Surface with search results
  test('06-surface-search', async ({ page }) => {
    await page.click('[data-testid="nav-rail-surface"]')
    await page.waitForSelector('[data-testid="surface-shell"]', { state: 'visible', timeout: 5000 })
    // Click search tab
    const searchTab = page.locator('[aria-label="Search"]').first()
    await searchTab.click()
    // Type in search
    const searchInput = page.locator('[aria-label="Search files and data catalog"]').first()
    await searchInput.fill('react')
    await page.waitForTimeout(500)
    await screenshot(page, '06-surface-search')
  })

  // 7. Both wings open (sessions + surface)
  test('07-both-wings-open', async ({ page }) => {
    await page.click('[data-testid="nav-rail-history"]')
    await page.waitForSelector('[data-testid="browse-drawer"]', { state: 'visible', timeout: 5000 })
    await page.click('[data-testid="nav-rail-surface"]')
    await page.waitForSelector('[data-testid="surface-shell"]', { state: 'visible', timeout: 5000 })
    await screenshot(page, '07-both-wings-open')
  })

  // 8. Chat with simulated messages (inject via evaluate)
  test('08-chat-with-messages', async ({ page }) => {
    // Inject messages via localStorage session state
    await page.evaluate(() => {
      const sessionId = 'demo-session-1'
      const state = {
        activeSessionId: sessionId,
        sessions: [{
          id: sessionId,
          title: 'Explore project structure',
          lastModified: Date.now(),
          status: 'active',
          draft: '',
          messages: [
            { id: 'm1', role: 'user', content: 'Show me the project structure', parts: [{ type: 'text', text: 'Show me the project structure' }] },
            { id: 'm2', role: 'assistant', content: 'Here is the project structure...', parts: [
              { type: 'text', text: "Here's the project structure:\n\n```\nsrc/\n  front/      — React frontend\n  server/     — TypeScript backend\n  shared/     — Shared types\ntests/        — Test files\ndocs/         — Documentation\n```\n\nThe project uses a **monorepo** layout with the frontend (React + Vite) and backend (Fastify + tRPC) in the same repo." },
            ]},
            { id: 'm3', role: 'user', content: 'What about the config files?', parts: [{ type: 'text', text: 'What about the config files?' }] },
            { id: 'm4', role: 'assistant', content: 'Key config files...', parts: [
              { type: 'text', text: "Key configuration files:\n\n- **`package.json`** — Dependencies and scripts\n- **`vite.config.ts`** — Vite build configuration with path aliases\n- **`tsconfig.json`** — TypeScript configuration\n- **`boring.app.toml`** — App configuration (workspace backend, agent settings)\n- **`tailwind.config.js`** — Tailwind CSS setup" },
            ]},
          ],
        }],
      }
      localStorage.setItem('boring-ui:chat-sessions:v1', JSON.stringify(state))
    })
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 })
    await waitForShell(page)
    await screenshot(page, '08-chat-with-messages')
  })

  // 9. Chat with tool call cards
  test('09-chat-with-tool-calls', async ({ page }) => {
    await page.evaluate(() => {
      const sessionId = 'demo-session-2'
      const state = {
        activeSessionId: sessionId,
        sessions: [{
          id: sessionId,
          title: 'File operations',
          lastModified: Date.now(),
          status: 'active',
          draft: '',
          messages: [
            { id: 't1', role: 'user', content: 'Create a hello.js file', parts: [{ type: 'text', text: 'Create a hello.js file' }] },
            { id: 't2', role: 'assistant', content: '', parts: [
              { type: 'text', text: "I'll create the file for you." },
              { type: 'tool-result', toolCallId: 'tc-1', toolName: 'write_file', input: { path: 'hello.js', content: 'console.log("Hello!")' }, output: 'File written: hello.js', status: 'complete' },
              { type: 'text', text: 'Done! Created `hello.js` with a simple hello world.' },
            ]},
            { id: 't3', role: 'user', content: 'Now read it back', parts: [{ type: 'text', text: 'Now read it back' }] },
            { id: 't4', role: 'assistant', content: '', parts: [
              { type: 'tool-result', toolCallId: 'tc-2', toolName: 'read_file', input: { path: 'hello.js' }, output: 'console.log("Hello!")', status: 'complete' },
              { type: 'text', text: 'The file contains:\n```js\nconsole.log("Hello!")\n```' },
            ]},
          ],
        }],
      }
      localStorage.setItem('boring-ui:chat-sessions:v1', JSON.stringify(state))
    })
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 })
    await waitForShell(page)
    await screenshot(page, '09-chat-with-tool-calls')
  })

  // 10. Narrow viewport (mobile-ish)
  test('10-narrow-viewport', async ({ page }) => {
    await page.setViewportSize({ width: 960, height: 900 })
    await page.waitForTimeout(500)
    await screenshot(page, '10-narrow-viewport')
  })

  // 11. Dark theme
  test('11-dark-theme', async ({ page }) => {
    await page.evaluate(() => {
      document.documentElement.setAttribute('data-theme', 'dark')
      localStorage.setItem('boring-ui-theme', 'dark')
    })
    await page.waitForTimeout(300)
    await screenshot(page, '11-dark-theme')
  })

  // 12. Dark theme with messages
  test('12-dark-theme-messages', async ({ page }) => {
    await page.evaluate(() => {
      document.documentElement.setAttribute('data-theme', 'dark')
      const sessionId = 'dark-demo'
      const state = {
        activeSessionId: sessionId,
        sessions: [{
          id: sessionId,
          title: 'Dark mode conversation',
          lastModified: Date.now(),
          status: 'active',
          draft: '',
          messages: [
            { id: 'd1', role: 'user', content: 'How does the auth system work?', parts: [{ type: 'text', text: 'How does the auth system work?' }] },
            { id: 'd2', role: 'assistant', content: '', parts: [
              { type: 'text', text: "The auth system uses **JWT session cookies**:\n\n1. User logs in via `/auth/login`\n2. Server creates an HS256-signed JWT with `sub`, `email`, `exp`\n3. Cookie is set as `boring_session` (httpOnly, sameSite: lax)\n4. All API routes validate the cookie via `createAuthHook`\n\nIn local dev mode, the server auto-creates a session on first request — no manual login needed." },
            ]},
          ],
        }],
      }
      localStorage.setItem('boring-ui:chat-sessions:v1', JSON.stringify(state))
    })
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 })
    await waitForShell(page)
    await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'))
    await page.waitForTimeout(300)
    await screenshot(page, '12-dark-theme-messages')
  })

  // 13. Surface collapsed (handle visible)
  test('13-surface-collapsed-handle', async ({ page }) => {
    // Open surface then close it to show the collapsed handle
    await page.click('[data-testid="nav-rail-surface"]')
    await page.waitForSelector('[data-testid="surface-shell"]', { state: 'visible', timeout: 5000 })
    await page.click('[data-testid="nav-rail-surface"]')
    await page.waitForTimeout(500)
    await screenshot(page, '13-surface-collapsed-handle')
  })

  // 14. Chat with reasoning block
  test('14-chat-with-reasoning', async ({ page }) => {
    await page.evaluate(() => {
      const sessionId = 'reasoning-demo'
      const state = {
        activeSessionId: sessionId,
        sessions: [{
          id: sessionId,
          title: 'Complex question',
          lastModified: Date.now(),
          status: 'active',
          draft: '',
          messages: [
            { id: 'r1', role: 'user', content: 'Should I use SSR or CSR for this project?', parts: [{ type: 'text', text: 'Should I use SSR or CSR for this project?' }] },
            { id: 'r2', role: 'assistant', content: '', parts: [
              { type: 'reasoning', reasoning: 'Let me consider the trade-offs. This is a developer tool (IDE-like), so it needs fast interactivity. SSR adds complexity for server rendering. The app is behind auth, so SEO doesn\'t matter. CSR with code splitting is the better fit.' },
              { type: 'text', text: "For this project, **CSR (Client-Side Rendering)** is the right choice:\n\n- **No SEO requirement** — it's behind auth\n- **Heavy interactivity** — DockView panels, real-time chat, terminal\n- **Code splitting** — Vite handles lazy-loading heavy chunks (editor, terminal, git)\n- **Simpler deployment** — static files + API server\n\nSSR would add complexity without meaningful benefit here." },
            ]},
          ],
        }],
      }
      localStorage.setItem('boring-ui:chat-sessions:v1', JSON.stringify(state))
    })
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 })
    await waitForShell(page)
    await screenshot(page, '14-chat-with-reasoning')
  })

  // 15. Multiple sessions in drawer
  test('15-multiple-sessions', async ({ page }) => {
    await page.evaluate(() => {
      const now = Date.now()
      const state = {
        activeSessionId: 'session-active',
        sessions: [
          { id: 'session-active', title: 'Fix auth middleware', lastModified: now, status: 'active', draft: '', messages: [{ id: 'x', role: 'user', content: 'Fix auth', parts: [{ type: 'text', text: 'Fix the auth middleware' }] }] },
          { id: 'session-paused', title: 'Refactor data provider', lastModified: now - 3600000, status: 'paused', draft: '', messages: [{ id: 'y', role: 'user', content: 'test', parts: [] }] },
          { id: 'session-old1', title: 'Setup CI pipeline', lastModified: now - 86400000, status: 'idle', draft: '', messages: [] },
          { id: 'session-old2', title: 'Review PR #42', lastModified: now - 86400000 - 7200000, status: 'idle', draft: '', messages: [] },
          { id: 'session-old3', title: 'Debug deploy script', lastModified: now - 172800000, status: 'idle', draft: '', messages: [] },
        ],
      }
      localStorage.setItem('boring-ui:chat-sessions:v1', JSON.stringify(state))
    })
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 })
    await waitForShell(page)
    await page.click('[data-testid="nav-rail-history"]')
    await page.waitForSelector('[data-testid="browse-drawer"]', { state: 'visible', timeout: 5000 })
    await page.waitForTimeout(500)
    await screenshot(page, '15-multiple-sessions')
  })
})
