import { describe, it, expect } from 'vitest'
import { createApp } from '../app.js'
import { testSessionCookie, TEST_SECRET } from './helpers.js'
import { loadConfig } from '../config.js'

function getApp() {
  return createApp({ config: { ...loadConfig(), sessionSecret: TEST_SECRET } as any, skipValidation: true })
}

describe('UI State routes', () => {
  it('PUT /ui/state saves state', async () => {
    const app = getApp()
    const token = await testSessionCookie()
    const res = await app.inject({
      method: 'PUT', url: '/api/v1/ui/state',
      cookies: { boring_session: token },
      payload: { client_id: 'test-client', panes: [{ id: 'filetree' }], active_panel: 'filetree' },
    })
    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.payload)
    expect(body.ok).toBe(true)
    await app.close()
  })

  it('GET /ui/state/latest returns saved state', async () => {
    const app = getApp()
    const token = await testSessionCookie()
    await app.inject({
      method: 'PUT', url: '/api/v1/ui/state',
      cookies: { boring_session: token },
      payload: { client_id: 'test', panes: [{ id: 'editor' }] },
    })
    const res = await app.inject({ method: 'GET', url: '/api/v1/ui/state/latest', cookies: { boring_session: token } })
    expect(res.statusCode).toBe(200)
    await app.close()
  })

  it('GET /ui/state lists all states', async () => {
    const app = getApp()
    const token = await testSessionCookie()
    const res = await app.inject({ method: 'GET', url: '/api/v1/ui/state', cookies: { boring_session: token } })
    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.payload)
    expect(body).toHaveProperty('states')
    await app.close()
  })

  it('POST /ui/commands enqueues command', async () => {
    const app = getApp()
    const token = await testSessionCookie()
    const res = await app.inject({
      method: 'POST', url: '/api/v1/ui/commands',
      cookies: { boring_session: token },
      payload: { type: 'focus_panel', payload: { panel_id: 'editor' } },
    })
    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.payload)
    expect(body.command.type).toBe('focus_panel')
    await app.close()
  })

  it('GET /ui/commands/next polls command', async () => {
    const app = getApp()
    const token = await testSessionCookie()
    await app.inject({
      method: 'POST', url: '/api/v1/ui/commands',
      cookies: { boring_session: token },
      payload: { type: 'open_panel', payload: { panel_id: 'shell' } },
    })
    const res = await app.inject({ method: 'GET', url: '/api/v1/ui/commands/next?client_id=default', cookies: { boring_session: token } })
    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.payload)
    expect(body.command).toBeTruthy()
    await app.close()
  })

  it('POST /ui/focus is shortcut', async () => {
    const app = getApp()
    const token = await testSessionCookie()
    const res = await app.inject({
      method: 'POST', url: '/api/v1/ui/focus',
      cookies: { boring_session: token },
      payload: { panel_id: 'terminal' },
    })
    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.payload)
    expect(body.command.type).toBe('focus_panel')
    await app.close()
  })

  it('returns 401 without auth', async () => {
    const app = getApp()
    const res = await app.inject({ method: 'GET', url: '/api/v1/ui/state' })
    expect(res.statusCode).toBe(401)
    await app.close()
  })
})
