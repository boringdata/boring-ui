import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { mkdirSync, writeFileSync, rmSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { loadConfig } from '../config.js'
import { createApp } from '../app.js'
import { execSync } from 'node:child_process'
import { testSessionCookie, TEST_SECRET } from './helpers.js'

const TEST_WORKSPACE = join(tmpdir(), `http-compat-test-${Date.now()}`)

beforeAll(() => {
  mkdirSync(TEST_WORKSPACE, { recursive: true })
  writeFileSync(join(TEST_WORKSPACE, 'hello.txt'), 'Hello World')
  mkdirSync(join(TEST_WORKSPACE, 'subdir'), { recursive: true })
  writeFileSync(join(TEST_WORKSPACE, 'subdir', 'nested.txt'), 'Nested content')
  execSync('git init && git add -A && git commit -m "init" --allow-empty', {
    cwd: TEST_WORKSPACE,
    env: { ...process.env, GIT_AUTHOR_NAME: 'Test', GIT_AUTHOR_EMAIL: 'test@test.com', GIT_COMMITTER_NAME: 'Test', GIT_COMMITTER_EMAIL: 'test@test.com' },
    stdio: 'ignore',
  })
})

afterAll(() => {
  rmSync(TEST_WORKSPACE, { recursive: true, force: true })
})

function getApp() {
  const config = { ...loadConfig(), workspaceRoot: TEST_WORKSPACE, sessionSecret: TEST_SECRET }
  return createApp({ config, skipValidation: true })
}

describe('File HTTP compat routes', () => {
  describe('GET /api/v1/files/list', () => {
    it('lists root directory', async () => {
      const app = getApp()
      const token = await testSessionCookie()
      const res = await app.inject({ method: 'GET', url: '/api/v1/files/list?path=.', cookies: { boring_session: token } })
      expect(res.statusCode).toBe(200)
      const body = JSON.parse(res.payload)
      expect(body).toHaveProperty('entries')
      expect(body.entries.some((e: any) => e.name === 'hello.txt')).toBe(true)
      expect(body.entries.some((e: any) => e.name === 'subdir' && e.is_dir)).toBe(true)
      await app.close()
    })

    it('returns 404 for non-existent directory', async () => {
      const app = getApp()
      const token = await testSessionCookie()
      const res = await app.inject({ method: 'GET', url: '/api/v1/files/list?path=nonexistent', cookies: { boring_session: token } })
      expect(res.statusCode).toBe(404)
      await app.close()
    })
  })

  describe('GET /api/v1/files/read', () => {
    it('reads a file', async () => {
      const app = getApp()
      const token = await testSessionCookie()
      const res = await app.inject({ method: 'GET', url: '/api/v1/files/read?path=hello.txt', cookies: { boring_session: token } })
      expect(res.statusCode).toBe(200)
      const body = JSON.parse(res.payload)
      expect(body.content).toBe('Hello World')
      await app.close()
    })

    it('returns 400 without path', async () => {
      const app = getApp()
      const token = await testSessionCookie()
      const res = await app.inject({ method: 'GET', url: '/api/v1/files/read', cookies: { boring_session: token } })
      expect(res.statusCode).toBe(400)
      await app.close()
    })

    it('returns 404 for non-existent file', async () => {
      const app = getApp()
      const token = await testSessionCookie()
      const res = await app.inject({ method: 'GET', url: '/api/v1/files/read?path=nope.txt', cookies: { boring_session: token } })
      expect(res.statusCode).toBe(404)
      await app.close()
    })
  })

  describe('PUT /api/v1/files/write', () => {
    it('writes a file', async () => {
      const app = getApp()
      const token = await testSessionCookie()
      const res = await app.inject({
        method: 'PUT', url: '/api/v1/files/write',
        cookies: { boring_session: token },
        payload: { path: 'new-file.txt', content: 'Created via API' },
      })
      expect(res.statusCode).toBe(200)
      expect(existsSync(join(TEST_WORKSPACE, 'new-file.txt'))).toBe(true)
      await app.close()
    })
  })

  describe('GET /api/v1/files/search', () => {
    it('finds files matching pattern', async () => {
      const app = getApp()
      const token = await testSessionCookie()
      const res = await app.inject({ method: 'GET', url: '/api/v1/files/search?pattern=hello*', cookies: { boring_session: token } })
      expect(res.statusCode).toBe(200)
      const body = JSON.parse(res.payload)
      expect(body.results.length).toBeGreaterThan(0)
      await app.close()
    })
  })
})

describe('Git HTTP compat routes', () => {
  describe('GET /api/v1/git/status', () => {
    it('returns git status', async () => {
      const app = getApp()
      const token = await testSessionCookie()
      const res = await app.inject({ method: 'GET', url: '/api/v1/git/status', cookies: { boring_session: token } })
      expect(res.statusCode).toBe(200)
      const body = JSON.parse(res.payload)
      expect(body.is_repo).toBe(true)
      await app.close()
    })
  })

  describe('GET /api/v1/git/branch', () => {
    it('returns current branch', async () => {
      const app = getApp()
      const token = await testSessionCookie()
      const res = await app.inject({ method: 'GET', url: '/api/v1/git/branch', cookies: { boring_session: token } })
      expect(res.statusCode).toBe(200)
      await app.close()
    })
  })

  describe('GET /api/v1/git/diff', () => {
    it('returns diff', async () => {
      const app = getApp()
      const token = await testSessionCookie()
      const res = await app.inject({ method: 'GET', url: '/api/v1/git/diff', cookies: { boring_session: token } })
      expect(res.statusCode).toBe(200)
      await app.close()
    })
  })
})
