import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { createApp } from '../app.js'
import { loadConfig } from '../config.js'
import { testSessionCookie, TEST_SECRET } from './helpers.js'

const TEST_WORKSPACE = join(tmpdir(), `exec-test-${Date.now()}`)

beforeAll(() => {
  mkdirSync(TEST_WORKSPACE, { recursive: true })
  writeFileSync(join(TEST_WORKSPACE, 'hello.txt'), 'Hello from workspace')
})

afterAll(() => {
  rmSync(TEST_WORKSPACE, { recursive: true, force: true })
})

function getApp() {
  const config = { ...loadConfig(), workspaceRoot: TEST_WORKSPACE, sessionSecret: TEST_SECRET }
  return createApp({ config, skipValidation: true })
}

describe('POST /api/v1/exec', () => {
  it('runs echo and captures stdout', async () => {
    const app = getApp()
    const token = await testSessionCookie()
    const res = await app.inject({
      method: 'POST', url: '/api/v1/exec',
      cookies: { boring_session: token },
      payload: { command: 'echo hello' },
    })
    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.payload)
    expect(body.stdout.trim()).toBe('hello')
    expect(body.exit_code).toBe(0)
    await app.close()
  })

  it('captures stderr', async () => {
    const app = getApp()
    const token = await testSessionCookie()
    const res = await app.inject({
      method: 'POST', url: '/api/v1/exec',
      cookies: { boring_session: token },
      payload: { command: 'echo error >&2' },
    })
    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.payload)
    expect(body.stderr.trim()).toBe('error')
    await app.close()
  })

  it('returns non-zero exit code on failure', async () => {
    const app = getApp()
    const token = await testSessionCookie()
    const res = await app.inject({
      method: 'POST', url: '/api/v1/exec',
      cookies: { boring_session: token },
      payload: { command: 'exit 42' },
    })
    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.payload)
    expect(body.exit_code).toBe(42)
    await app.close()
  })

  it('rejects empty command', async () => {
    const app = getApp()
    const token = await testSessionCookie()
    const res = await app.inject({
      method: 'POST', url: '/api/v1/exec',
      cookies: { boring_session: token },
      payload: { command: '' },
    })
    expect(res.statusCode).toBe(400)
    await app.close()
  })

  it('rejects missing command', async () => {
    const app = getApp()
    const token = await testSessionCookie()
    const res = await app.inject({
      method: 'POST', url: '/api/v1/exec',
      cookies: { boring_session: token },
      payload: {},
    })
    expect(res.statusCode).toBe(400)
    await app.close()
  })

  it('rejects cwd path traversal', async () => {
    const app = getApp()
    const token = await testSessionCookie()
    const res = await app.inject({
      method: 'POST', url: '/api/v1/exec',
      cookies: { boring_session: token },
      payload: { command: 'ls', cwd: '../../../etc' },
    })
    expect(res.statusCode).toBe(400)
    await app.close()
  })

  it('returns 401 without auth', async () => {
    const app = getApp()
    const res = await app.inject({
      method: 'POST', url: '/api/v1/exec',
      payload: { command: 'echo hello' },
    })
    expect(res.statusCode).toBe(401)
    await app.close()
  })
})
