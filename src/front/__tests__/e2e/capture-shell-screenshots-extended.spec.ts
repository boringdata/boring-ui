/**
 * Extended Shell UI Screenshots — states not covered in the first 15.
 */
import { test, expect, type Page, type Route } from '@playwright/test'
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
        ], path: '.',
      })
    }
    if (p === 'src') {
      return fulfillJson(route, 200, {
        entries: [
          { name: 'front', path: 'src/front', is_dir: true },
          { name: 'server', path: 'src/server', is_dir: true },
          { name: 'shared', path: 'src/shared', is_dir: true },
        ], path: 'src',
      })
    }
    if (p === 'src/front') {
      return fulfillJson(route, 200, {
        entries: [
          { name: 'App.jsx', path: 'src/front/App.jsx', is_dir: false },
          { name: 'main.jsx', path: 'src/front/main.jsx', is_dir: false },
          { name: 'layouts', path: 'src/front/layouts', is_dir: true },
          { name: 'shared', path: 'src/front/shared', is_dir: true },
        ], path: 'src/front',
      })
    }
    return fulfillJson(route, 200, { entries: [], path: p })
  })
  await page.route('**/api/v1/files/read**', (route) => {
    const url = new URL(route.request().url())
    const p = url.searchParams.get('path') || ''
    if (p.endsWith('.md')) {
      return fulfillJson(route, 200, { content: '# Welcome\n\nProject documentation.\n', path: p })
    }
    if (p.endsWith('.json')) {
      return fulfillJson(route, 200, { content: '{\n  "name": "boring-ui",\n  "version": "0.1.0"\n}\n', path: p })
    }
    return fulfillJson(route, 200, { content: 'import React from "react"\n\nexport default function App() {\n  return <div>Hello</div>\n}\n', path: p })
  })
  await page.route('**/api/v1/files/search**', (route) =>
    fulfillJson(route, 200, {
      results: [
        { path: 'src/front/App.jsx', line_number: 1, line: 'import React from "react"' },
        { path: 'src/front/main.jsx', line_number: 3, line: 'import App from "./App"' },
        { path: 'src/server/index.ts', line_number: 5, line: 'const app = createApp()' },
        { path: 'README.md', line_number: 3, line: '## Getting Started' },
        { path: 'docs/ARCHITECTURE.md', line_number: 10, line: 'The system uses React + Fastify' },
      ],
    }),
  )
  await page.route('**/api/v1/git/status', (route) =>
    fulfillJson(route, 200, {
      is_repo: true,
      files: [
        { path: 'src/front/App.jsx', status: 'M' },
        { path: 'src/front/layouts/chat/layout.css', status: 'M' },
        { path: 'src/front/shared/design-system/tokens.css', status: 'M' },
      ],
    }),
  )
  await page.route('**/api/config**', (route) => fulfillJson(route, 200, {}))
  await page.route('**/api/tree**', (route) =>
    fulfillJson(route, 200, [
      { name: 'src', path: 'src', is_dir: true },
      { name: 'docs', path: 'docs', is_dir: true },
      { name: 'package.json', path: 'package.json', is_dir: false },
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

function injectSession(id: string, title: string, messages: any[], status = 'active') {
  return { id, title, lastModified: Date.now(), status, draft: '', messages }
}

test.describe('Extended Shell Screenshots', () => {
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

  // 16. Tool call in running state (spinner)
  test('16-tool-running', async ({ page }) => {
    await page.evaluate(() => {
      const state = {
        activeSessionId: 's-running',
        sessions: [{ id: 's-running', title: 'Running tools', lastModified: Date.now(), status: 'active', draft: '', messages: [
          { id: 'r1', role: 'user', content: 'Search for all React components', parts: [{ type: 'text', text: 'Search for all React components' }] },
          { id: 'r2', role: 'assistant', content: '', parts: [
            { type: 'text', text: 'Let me search the codebase for React components.' },
            { type: 'tool-call', toolCallId: 'tc-run-1', toolName: 'grep', input: { pattern: 'export default function', path: 'src/' } },
            { type: 'tool-call', toolCallId: 'tc-run-2', toolName: 'bash', input: { command: 'find src/ -name "*.jsx" | wc -l' } },
          ]},
        ]}],
      }
      localStorage.setItem('boring-ui:chat-sessions:v1', JSON.stringify(state))
    })
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 })
    await waitForShell(page)
    await screenshot(page, '16-tool-running')
  })

  // 17. Multi-tool completed (bash + grep + write)
  test('17-multi-tool-complete', async ({ page }) => {
    await page.evaluate(() => {
      const state = {
        activeSessionId: 's-multi',
        sessions: [{ id: 's-multi', title: 'Multi-tool operation', lastModified: Date.now(), status: 'active', draft: '', messages: [
          { id: 'm1', role: 'user', content: 'Find all test files and create a summary', parts: [{ type: 'text', text: 'Find all test files and create a summary' }] },
          { id: 'm2', role: 'assistant', content: '', parts: [
            { type: 'text', text: "I'll search for test files and create a summary." },
            { type: 'tool-result', toolCallId: 'tc-m1', toolName: 'bash', input: { command: 'find src/ -name "*.test.*" | head -10' }, output: 'src/front/App.test.jsx\nsrc/front/shared/hooks/useSessionState.test.js\nsrc/front/shared/utils/sanitize.test.js\nsrc/server/config.test.ts\nsrc/server/auth/session.test.ts' },
            { type: 'tool-result', toolCallId: 'tc-m2', toolName: 'grep', input: { pattern: 'describe\\(', path: 'src/' }, output: 'src/front/App.test.jsx:5:describe("App",\nsrc/server/config.test.ts:3:describe("loadConfig",' },
            { type: 'tool-result', toolCallId: 'tc-m3', toolName: 'write_file', input: { path: 'TEST_SUMMARY.md', content: '# Test Summary\n\n- 5 test files found\n- 2 describe blocks\n' }, output: 'File written: TEST_SUMMARY.md' },
            { type: 'text', text: "Done! Found **5 test files** across frontend and backend. Created `TEST_SUMMARY.md` with the summary.\n\nKey test areas:\n- **Frontend**: App, hooks, utilities\n- **Backend**: Config, auth session" },
          ]},
        ]}],
      }
      localStorage.setItem('boring-ui:chat-sessions:v1', JSON.stringify(state))
    })
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 })
    await waitForShell(page)
    await screenshot(page, '17-multi-tool-complete')
  })

  // 18. Dark theme with tool calls
  test('18-dark-tool-calls', async ({ page }) => {
    await page.evaluate(() => {
      document.documentElement.setAttribute('data-theme', 'dark')
      const state = {
        activeSessionId: 's-dark-tool',
        sessions: [{ id: 's-dark-tool', title: 'Dark mode tools', lastModified: Date.now(), status: 'active', draft: '', messages: [
          { id: 'd1', role: 'user', content: 'Read the config file', parts: [{ type: 'text', text: 'Read the config file' }] },
          { id: 'd2', role: 'assistant', content: '', parts: [
            { type: 'tool-result', toolCallId: 'tc-d1', toolName: 'read_file', input: { path: 'tsconfig.json' }, output: '{\n  "compilerOptions": {\n    "target": "ES2020",\n    "jsx": "react-jsx"\n  }\n}' },
            { type: 'text', text: 'The TypeScript config uses **ES2020** target with **react-jsx** transform.' },
          ]},
        ]}],
      }
      localStorage.setItem('boring-ui:chat-sessions:v1', JSON.stringify(state))
    })
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 })
    await waitForShell(page)
    await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'))
    await page.waitForTimeout(300)
    await screenshot(page, '18-dark-tool-calls')
  })

  // 19. Dark theme with sessions drawer
  test('19-dark-sessions-drawer', async ({ page }) => {
    await page.evaluate(() => {
      document.documentElement.setAttribute('data-theme', 'dark')
      const now = Date.now()
      const state = {
        activeSessionId: 'ds-active',
        sessions: [
          { id: 'ds-active', title: 'Refactor auth module', lastModified: now, status: 'active', draft: '', messages: [{ id: 'x', role: 'user', content: 'test', parts: [{ type: 'text', text: 'Refactor the auth module' }] }] },
          { id: 'ds-paused', title: 'Debug CI pipeline', lastModified: now - 1800000, status: 'paused', draft: '', messages: [{ id: 'y', role: 'user', content: 'test', parts: [] }] },
          { id: 'ds-old', title: 'Add unit tests', lastModified: now - 86400000, status: 'idle', draft: '', messages: [] },
        ],
      }
      localStorage.setItem('boring-ui:chat-sessions:v1', JSON.stringify(state))
    })
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 })
    await waitForShell(page)
    await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'))
    await page.click('[data-testid="nav-rail-history"]')
    await page.waitForSelector('[data-testid="browse-drawer"]', { state: 'visible', timeout: 5000 })
    await page.waitForTimeout(300)
    await screenshot(page, '19-dark-sessions-drawer')
  })

  // 20. Dark theme with surface + file tree
  test('20-dark-surface-filetree', async ({ page }) => {
    await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'))
    await page.click('[data-testid="nav-rail-surface"]')
    await page.waitForSelector('[data-testid="surface-shell"]', { state: 'visible', timeout: 5000 })
    await page.waitForTimeout(800)
    await screenshot(page, '20-dark-surface-filetree')
  })

  // 21. Surface search with results
  test('21-surface-search-results', async ({ page }) => {
    await page.click('[data-testid="nav-rail-surface"]')
    await page.waitForSelector('[data-testid="surface-shell"]', { state: 'visible', timeout: 5000 })
    const searchTab = page.locator('[aria-label="Search"]').first()
    await searchTab.click()
    const searchInput = page.locator('[aria-label="Search files and data catalog"]').first()
    await searchInput.fill('React')
    await page.waitForTimeout(800)
    await screenshot(page, '21-surface-search-results')
  })

  // 22. File tree expanded (subdirectories open)
  test('22-filetree-expanded', async ({ page }) => {
    await page.click('[data-testid="nav-rail-surface"]')
    await page.waitForSelector('[data-testid="surface-shell"]', { state: 'visible', timeout: 5000 })
    await page.waitForTimeout(500)
    // Click on 'src' folder to expand
    const srcFolder = page.locator('.file-item-name', { hasText: 'src' }).first()
    if (await srcFolder.isVisible()) {
      await srcFolder.click()
      await page.waitForTimeout(500)
      // Try to expand src/front
      const frontFolder = page.locator('.file-item-name', { hasText: 'front' }).first()
      if (await frontFolder.isVisible()) {
        await frontFolder.click()
        await page.waitForTimeout(500)
      }
    }
    await screenshot(page, '22-filetree-expanded')
  })

  // 23. Chat with long code block
  test('23-long-code-block', async ({ page }) => {
    await page.evaluate(() => {
      const state = {
        activeSessionId: 's-code',
        sessions: [{ id: 's-code', title: 'Code generation', lastModified: Date.now(), status: 'active', draft: '', messages: [
          { id: 'c1', role: 'user', content: 'Write a React hook for dark mode', parts: [{ type: 'text', text: 'Write a React hook for dark mode' }] },
          { id: 'c2', role: 'assistant', content: '', parts: [
            { type: 'text', text: "Here's a `useDarkMode` hook:\n\n```typescript\nimport { useState, useEffect } from 'react'\n\nexport function useDarkMode() {\n  const [isDark, setIsDark] = useState(() => {\n    const stored = localStorage.getItem('theme')\n    if (stored) return stored === 'dark'\n    return window.matchMedia('(prefers-color-scheme: dark)').matches\n  })\n\n  useEffect(() => {\n    const root = document.documentElement\n    if (isDark) {\n      root.setAttribute('data-theme', 'dark')\n      localStorage.setItem('theme', 'dark')\n    } else {\n      root.setAttribute('data-theme', 'light')\n      localStorage.setItem('theme', 'light')\n    }\n  }, [isDark])\n\n  const toggle = () => setIsDark(prev => !prev)\n\n  return { isDark, toggle }\n}\n```\n\nUsage:\n```tsx\nfunction App() {\n  const { isDark, toggle } = useDarkMode()\n  return <button onClick={toggle}>{isDark ? '☀️' : '🌙'}</button>\n}\n```" },
          ]},
        ]}],
      }
      localStorage.setItem('boring-ui:chat-sessions:v1', JSON.stringify(state))
    })
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 })
    await waitForShell(page)
    await screenshot(page, '23-long-code-block')
  })

  // 24. Chat with error state
  test('24-chat-error', async ({ page }) => {
    await page.evaluate(() => {
      const state = {
        activeSessionId: 's-err',
        sessions: [{ id: 's-err', title: 'Error handling', lastModified: Date.now(), status: 'active', draft: '', messages: [
          { id: 'e1', role: 'user', content: 'Delete all files', parts: [{ type: 'text', text: 'Delete all files' }] },
          { id: 'e2', role: 'assistant', content: '', parts: [
            { type: 'tool-result', toolCallId: 'tc-err', toolName: 'bash', input: { command: 'rm -rf /' }, output: '', status: 'error', isError: true },
            { type: 'tool-error', toolCallId: 'tc-err', toolName: 'bash', error: 'Permission denied: cannot execute destructive commands' },
            { type: 'text', text: "I can't execute that command — it would delete all files on the system. This operation is blocked for safety.\n\nIf you want to clean up specific files, please tell me which ones." },
          ]},
        ]}],
      }
      localStorage.setItem('boring-ui:chat-sessions:v1', JSON.stringify(state))
    })
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 })
    await waitForShell(page)
    await screenshot(page, '24-chat-error')
  })

  // 25. Both wings + messages (realistic working state)
  test('25-full-workspace', async ({ page }) => {
    await page.evaluate(() => {
      const state = {
        activeSessionId: 's-full',
        sessions: [
          { id: 's-full', title: 'Working on auth', lastModified: Date.now(), status: 'active', draft: '', messages: [
            { id: 'f1', role: 'user', content: 'Show me the auth middleware', parts: [{ type: 'text', text: 'Show me the auth middleware' }] },
            { id: 'f2', role: 'assistant', content: '', parts: [
              { type: 'tool-result', toolCallId: 'tc-f1', toolName: 'read_file', input: { path: 'src/server/auth/middleware.ts' }, output: 'export function createAuthHook(app) { ... }' },
              { type: 'text', text: 'The auth middleware validates session cookies on every authenticated request.' },
            ]},
          ]},
          { id: 's-old', title: 'Setup project', lastModified: Date.now() - 3600000, status: 'idle', draft: '', messages: [] },
        ],
      }
      localStorage.setItem('boring-ui:chat-sessions:v1', JSON.stringify(state))
    })
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 })
    await waitForShell(page)
    // Open sessions drawer
    await page.click('[data-testid="nav-rail-history"]')
    await page.waitForSelector('[data-testid="browse-drawer"]', { state: 'visible', timeout: 5000 })
    // Open surface
    await page.click('[data-testid="nav-rail-surface"]')
    await page.waitForSelector('[data-testid="surface-shell"]', { state: 'visible', timeout: 5000 })
    await page.waitForTimeout(500)
    await screenshot(page, '25-full-workspace')
  })

  // 26. Dark theme full workspace
  test('26-dark-full-workspace', async ({ page }) => {
    await page.evaluate(() => {
      document.documentElement.setAttribute('data-theme', 'dark')
      const state = {
        activeSessionId: 's-dark-full',
        sessions: [
          { id: 's-dark-full', title: 'Fixing deploy script', lastModified: Date.now(), status: 'active', draft: '', messages: [
            { id: 'df1', role: 'user', content: 'What does the deploy script do?', parts: [{ type: 'text', text: 'What does the deploy script do?' }] },
            { id: 'df2', role: 'assistant', content: '', parts: [
              { type: 'tool-result', toolCallId: 'tc-df1', toolName: 'read_file', input: { path: 'deploy/modal_app.py' }, output: 'app = modal.App("boring-ui")' },
              { type: 'text', text: "The deploy script uses **Modal** to deploy the app. It creates a Modal app named `boring-ui` and configures the container with the built frontend assets." },
            ]},
          ]},
          { id: 's-dark-other', title: 'Review PR', lastModified: Date.now() - 7200000, status: 'paused', draft: '', messages: [{ id: 'x', role: 'user', content: 'test', parts: [] }] },
        ],
      }
      localStorage.setItem('boring-ui:chat-sessions:v1', JSON.stringify(state))
    })
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 })
    await waitForShell(page)
    await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'))
    await page.click('[data-testid="nav-rail-history"]')
    await page.waitForSelector('[data-testid="browse-drawer"]', { state: 'visible', timeout: 5000 })
    await page.click('[data-testid="nav-rail-surface"]')
    await page.waitForSelector('[data-testid="surface-shell"]', { state: 'visible', timeout: 5000 })
    await page.waitForTimeout(500)
    await screenshot(page, '26-dark-full-workspace')
  })

  // 27. Composer with multiline input
  test('27-multiline-composer', async ({ page }) => {
    const input = page.locator('.vc-composer-input')
    await input.click()
    await input.fill('Can you help me with the following tasks:\n1. Review the auth middleware for security issues\n2. Add rate limiting to the API endpoints\n3. Write unit tests for the session cookie handling')
    await page.waitForTimeout(300)
    await screenshot(page, '27-multiline-composer')
  })
})
