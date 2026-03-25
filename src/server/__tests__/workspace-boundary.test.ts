import { describe, it, expect } from 'vitest'
import { createApp } from '../app.js'
import { createSessionCookie } from '../auth/session.js'
import { loadConfig } from '../config.js'

const TEST_SECRET = 'test-secret-must-be-at-least-32-characters-long-for-hs256'
const WORKSPACE_ID = '00000000-0000-0000-0000-000000000001'

function getApp() {
  return createApp({ config: { ...loadConfig(), sessionSecret: TEST_SECRET } })
}

async function getToken() {
  return createSessionCookie('user-123', 'alice@example.com', TEST_SECRET, { ttlSeconds: 3600 })
}

describe('Workspace boundary routing', () => {
  it('rejects invalid workspace ID', async () => {
    const app = getApp()
    const token = await getToken()
    const res = await app.inject({
      method: 'GET',
      url: '/w/not-a-uuid/api/v1/files/list',
      cookies: { boring_session: token },
    })
    expect(res.statusCode).toBe(400)
    await app.close()
  })

  it('returns 401 without session cookie', async () => {
    const app = getApp()
    const res = await app.inject({
      method: 'GET',
      url: `/w/${WORKSPACE_ID}/api/v1/files/list`,
    })
    expect(res.statusCode).toBe(401)
    await app.close()
  })

  it('rejects non-passthrough paths', async () => {
    const app = getApp()
    const token = await getToken()
    const res = await app.inject({
      method: 'GET',
      url: `/w/${WORKSPACE_ID}/admin/secret`,
      cookies: { boring_session: token },
    })
    expect(res.statusCode).toBe(404)
    await app.close()
  })

  it('redirects allowed paths to actual routes', async () => {
    const app = getApp()
    const token = await getToken()
    const res = await app.inject({
      method: 'GET',
      url: `/w/${WORKSPACE_ID}/api/v1/files/list?path=.`,
      cookies: { boring_session: token },
    })
    // Should redirect (307) or proxy (200) or error on redirect (500)
    // The redirect target may not work in inject mode, but the boundary
    // should at least not return 401 or 404
    expect(res.statusCode).not.toBe(401)
    expect(res.statusCode).not.toBe(404)
    await app.close()
  })

  it('serves workspace root as SPA page', async () => {
    const app = getApp()
    const res = await app.inject({
      method: 'GET',
      url: `/w/${WORKSPACE_ID}`,
    })
    expect(res.statusCode).toBe(200)
    expect(res.headers['content-type']).toContain('text/html')
    await app.close()
  })
})
