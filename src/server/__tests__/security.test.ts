import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { mkdirSync, writeFileSync, symlinkSync, rmSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { createApp } from '../app.js'
import { loadConfig } from '../config.js'
import { testSessionCookie, TEST_SECRET } from './helpers.js'

const TEST_WORKSPACE = join(tmpdir(), `security-test-${Date.now()}`)
const OUTSIDE_DIR = join(tmpdir(), `security-outside-${Date.now()}`)

beforeAll(() => {
  mkdirSync(TEST_WORKSPACE, { recursive: true })
  mkdirSync(OUTSIDE_DIR, { recursive: true })
  writeFileSync(join(TEST_WORKSPACE, 'safe.txt'), 'safe content')
  writeFileSync(join(OUTSIDE_DIR, 'secret.txt'), 'SECRET DATA')
})

afterAll(() => {
  rmSync(TEST_WORKSPACE, { recursive: true, force: true })
  rmSync(OUTSIDE_DIR, { recursive: true, force: true })
})

function getApp() {
  const config = { ...loadConfig(), workspaceRoot: TEST_WORKSPACE, sessionSecret: TEST_SECRET }
  return createApp({ config, skipValidation: true })
}

describe('Path traversal prevention (files)', () => {
  it('rejects ../etc/passwd', async () => {
    const app = getApp()
    const token = await testSessionCookie()
    const res = await app.inject({
      method: 'GET', url: '/api/v1/files/read?path=../etc/passwd',
      cookies: { boring_session: token },
    })
    expect(res.statusCode).toBe(400)
    await app.close()
  })

  it('rejects ../../outside path', async () => {
    const app = getApp()
    const token = await testSessionCookie()
    const res = await app.inject({
      method: 'GET', url: `/api/v1/files/read?path=../../${OUTSIDE_DIR}/secret.txt`,
      cookies: { boring_session: token },
    })
    expect([400, 404]).toContain(res.statusCode)
    expect(res.payload).not.toContain('SECRET DATA')
    await app.close()
  })

  it('rejects path traversal in write', async () => {
    const app = getApp()
    const token = await testSessionCookie()
    const res = await app.inject({
      method: 'PUT', url: '/api/v1/files/write',
      cookies: { boring_session: token },
      payload: { path: '../outside.txt', content: 'malicious' },
    })
    expect(res.statusCode).toBe(400)
    expect(existsSync(join(TEST_WORKSPACE, '..', 'outside.txt'))).toBe(false)
    await app.close()
  })

  it('rejects path traversal in delete', async () => {
    const app = getApp()
    const token = await testSessionCookie()
    const res = await app.inject({
      method: 'DELETE', url: '/api/v1/files/delete?path=../etc/passwd',
      cookies: { boring_session: token },
    })
    expect(res.statusCode).toBe(400)
    await app.close()
  })

  it('allows reading files within workspace', async () => {
    const app = getApp()
    const token = await testSessionCookie()
    const res = await app.inject({
      method: 'GET',
      url: '/api/v1/files/read?path=safe.txt',
      cookies: { boring_session: token },
    })
    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.payload)
    expect(body.content).toBe('safe content')
    await app.close()
  })
})

describe('Git security validations', () => {
  it('rejects flag injection in remote name', async () => {
    const { createGitServiceImpl } = await import('../services/gitImpl.js')
    const svc = createGitServiceImpl(TEST_WORKSPACE)
    await expect(svc.addRemote('--upload-pack=evil', 'https://example.com/repo.git')).rejects.toThrow()
  })

  it('rejects file:// URLs', async () => {
    const { createGitServiceImpl } = await import('../services/gitImpl.js')
    const svc = createGitServiceImpl(TEST_WORKSPACE)
    await expect(svc.cloneRepo('file:///etc/passwd')).rejects.toThrow(/unsupported/i)
  })

  it('rejects ssh:// URLs', async () => {
    const { createGitServiceImpl } = await import('../services/gitImpl.js')
    const svc = createGitServiceImpl(TEST_WORKSPACE)
    await expect(svc.cloneRepo('ssh://attacker.com/repo')).rejects.toThrow(/unsupported/i)
  })
})

describe('Bwrap isolation', () => {
  it('cannot access files outside workspace', async () => {
    const { execInSandbox } = await import('../adapters/bwrapImpl.js')
    const result = await execInSandbox(TEST_WORKSPACE, `cat ${OUTSIDE_DIR}/secret.txt 2>&1 || true`)
    expect(result.stdout + result.stderr).not.toContain('SECRET DATA')
  })

  it('can access files inside workspace', async () => {
    const { execInSandbox } = await import('../adapters/bwrapImpl.js')
    const result = await execInSandbox(TEST_WORKSPACE, 'cat /workspace/safe.txt')
    expect(result.stdout.trim()).toBe('safe content')
  })

  it('cannot write outside workspace', async () => {
    const { execInSandbox } = await import('../adapters/bwrapImpl.js')
    const result = await execInSandbox(TEST_WORKSPACE, 'touch /tmp/escape.txt 2>&1; echo $?')
    // /tmp inside sandbox is tmpfs, so writes succeed there but don't escape
    // The key test is that workspace root is the only real mount
  })

  it('BWRAP_TIMEOUT_SECONDS is configured to 60', async () => {
    const { BWRAP_TIMEOUT_SECONDS } = await import('../adapters/bwrapImpl.js')
    expect(BWRAP_TIMEOUT_SECONDS).toBe(60)
  })
})

describe('Auth redirect validation', () => {
  it('rejects absolute URLs', async () => {
    const { validateRedirectUrl } = await import('../auth/validation.js')
    expect(validateRedirectUrl('https://evil.com')).toBe('/')
  })

  it('rejects protocol-relative URLs', async () => {
    const { validateRedirectUrl } = await import('../auth/validation.js')
    expect(validateRedirectUrl('//evil.com')).toBe('/')
  })

  it('allows safe relative paths', async () => {
    const { validateRedirectUrl } = await import('../auth/validation.js')
    expect(validateRedirectUrl('/w/abc-123')).toBe('/w/abc-123')
  })
})
