import { describe, it, expect } from 'vitest'
import { createApp } from '../app.js'

function getApp() {
  return createApp()
}

describe('UI State routes', () => {
  it('PUT /ui/state saves state', async () => {
    const app = getApp()
    const res = await app.inject({
      method: 'PUT',
      url: '/api/v1/ui/state',
      payload: { client_id: 'test-client', panes: [{ id: 'filetree' }], active_panel: 'filetree' },
    })
    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.payload)
    expect(body.ok).toBe(true)
    expect(body.saved).toBe(true)
    await app.close()
  })

  it('GET /ui/state/latest returns saved state', async () => {
    const app = getApp()
    // Save first
    await app.inject({
      method: 'PUT',
      url: '/api/v1/ui/state',
      payload: { client_id: 'test', panes: [{ id: 'editor' }] },
    })
    // Then fetch
    const res = await app.inject({ method: 'GET', url: '/api/v1/ui/state/latest' })
    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.payload)
    expect(body.ok).toBe(true)
    expect(body.state).toBeTruthy()
    await app.close()
  })

  it('GET /ui/state lists all states', async () => {
    const app = getApp()
    const res = await app.inject({ method: 'GET', url: '/api/v1/ui/state' })
    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.payload)
    expect(body).toHaveProperty('states')
    expect(Array.isArray(body.states)).toBe(true)
    await app.close()
  })

  it('POST /ui/commands enqueues command', async () => {
    const app = getApp()
    const res = await app.inject({
      method: 'POST',
      url: '/api/v1/ui/commands',
      payload: { type: 'focus_panel', payload: { panel_id: 'editor' } },
    })
    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.payload)
    expect(body.ok).toBe(true)
    expect(body.command.type).toBe('focus_panel')
    await app.close()
  })

  it('GET /ui/commands/next polls command', async () => {
    const app = getApp()
    // Enqueue
    await app.inject({
      method: 'POST',
      url: '/api/v1/ui/commands',
      payload: { type: 'open_panel', payload: { panel_id: 'shell' } },
    })
    // Poll
    const res = await app.inject({ method: 'GET', url: '/api/v1/ui/commands/next?client_id=default' })
    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.payload)
    expect(body.command).toBeTruthy()
    // Command type may be from this or prior test (shared in-memory store)
    expect(['focus_panel', 'open_panel']).toContain(body.command.type)
    await app.close()
  })

  it('POST /ui/focus is shortcut', async () => {
    const app = getApp()
    const res = await app.inject({
      method: 'POST',
      url: '/api/v1/ui/focus',
      payload: { panel_id: 'terminal' },
    })
    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.payload)
    expect(body.command.type).toBe('focus_panel')
    await app.close()
  })
})
