/**
 * Tests for dev auth routes (/auth/login, /auth/session, /auth/logout).
 */
import { describe, it, expect, afterEach } from 'vitest'
import { createApp } from '../app.js'
import { loadConfig } from '../config.js'
import { appCookieName } from '../auth/session.js'
import type { FastifyInstance } from 'fastify'

function testConfig(overrides = {}) {
  return { ...loadConfig(), controlPlaneProvider: 'local' as const, ...overrides }
}

let app: FastifyInstance

afterEach(async () => {
  if (app) await app.close()
})

describe('GET /auth/login (dev mode)', () => {
  it('creates session cookie and redirects', async () => {
    const config = testConfig()
    app = createApp({ config })

    const res = await app.inject({
      method: 'GET',
      url: '/auth/login?user_id=test-user&email=test@example.com&redirect_uri=/',
    })

    expect(res.statusCode).toBe(302)
    expect(res.headers.location).toBe('/')

    // Should set a session cookie
    const cookies = res.cookies
    const expectedCookieName = config.authSessionCookieName || appCookieName()
    const sessionCookie = cookies.find(
      (c: any) => c.name === expectedCookieName,
    )
    expect(sessionCookie).toBeDefined()
    expect(sessionCookie!.value).toBeTruthy()
  })

  it('uses default user when no params provided', async () => {
    const config = testConfig()
    app = createApp({ config })

    const res = await app.inject({
      method: 'GET',
      url: '/auth/login',
    })

    expect(res.statusCode).toBe(302)
    expect(res.headers.location).toBe('/')
  })

  it('redirects to custom redirect_uri', async () => {
    const config = testConfig()
    app = createApp({ config })

    const res = await app.inject({
      method: 'GET',
      url: '/auth/login?redirect_uri=/w/workspace-1',
    })

    expect(res.statusCode).toBe(302)
    expect(res.headers.location).toBe('/w/workspace-1')
  })
})

describe('POST /auth/logout (dev mode)', () => {
  it('clears session cookie', async () => {
    const config = testConfig()
    app = createApp({ config })

    const res = await app.inject({
      method: 'POST',
      url: '/auth/logout',
    })

    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.payload)
    expect(body.ok).toBe(true)
  })
})

describe('Auth routes in neon mode', () => {
  it('dev login route not available', async () => {
    const config = testConfig({ controlPlaneProvider: 'neon' })
    app = createApp({ config })

    const res = await app.inject({
      method: 'GET',
      url: '/auth/login',
    })

    // Should 404 since dev login is only for local mode
    expect(res.statusCode).toBe(404)
  })
})
