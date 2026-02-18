import { describe, expect, it } from 'vitest'
import { routes } from './routes'

describe('routes helper', () => {
  it('builds canonical file routes with encoded query object payloads', () => {
    expect(routes.files.read('src/App.jsx')).toEqual({
      path: '/api/v1/files/read',
      query: { path: 'src/App.jsx' },
    })

    expect(routes.files.search('needle')).toEqual({
      path: '/api/v1/files/search',
      query: { q: 'needle' },
    })
  })

  it('builds config route descriptors with optional query values', () => {
    expect(routes.config.get()).toEqual({
      path: '/api/config',
      query: undefined,
    })
    expect(routes.config.get('/tmp/app.config.js')).toEqual({
      path: '/api/config',
      query: { config_path: '/tmp/app.config.js' },
    })
  })

  it('builds websocket route descriptors without feature-local literals', () => {
    expect(routes.ws.plugins()).toEqual({ path: '/ws/plugins', query: undefined })
    expect(routes.ws.claudeStream({ session_id: 'abc' })).toEqual({
      path: '/ws/agent/normal/stream',
      query: { session_id: 'abc' },
    })
  })

  it('builds canonical control-plane route descriptors', () => {
    expect(routes.controlPlane.me.get()).toEqual({
      path: '/api/v1/me',
      query: undefined,
    })
    expect(routes.controlPlane.workspaces.list()).toEqual({
      path: '/api/v1/workspaces',
      query: undefined,
    })
    expect(routes.controlPlane.workspaces.create()).toEqual({
      path: '/api/v1/workspaces',
      query: undefined,
    })
    expect(routes.controlPlane.workspaces.runtime.get('ws-123')).toEqual({
      path: '/api/v1/workspaces/ws-123/runtime',
      query: undefined,
    })
    expect(routes.controlPlane.workspaces.runtime.retry('ws-123')).toEqual({
      path: '/api/v1/workspaces/ws-123/runtime/retry',
      query: undefined,
    })
    expect(routes.controlPlane.workspaces.settings.get('ws-123')).toEqual({
      path: '/api/v1/workspaces/ws-123/settings',
      query: undefined,
    })
    expect(routes.controlPlane.workspaces.settings.update('ws-123')).toEqual({
      path: '/api/v1/workspaces/ws-123/settings',
      query: undefined,
    })
    expect(routes.controlPlane.auth.logout()).toEqual({
      path: '/auth/logout',
      query: undefined,
    })
  })

  it('builds canonical workspace navigation paths', () => {
    expect(routes.controlPlane.workspaces.scope('ws-123')).toEqual({
      path: '/w/ws-123/',
      query: undefined,
    })
    expect(routes.controlPlane.workspaces.scope('ws-123', '/app/editor')).toEqual({
      path: '/w/ws-123/app/editor',
      query: undefined,
    })
    expect(routes.controlPlane.workspaces.setup('ws-123')).toEqual({
      path: '/w/ws-123/setup',
      query: undefined,
    })
  })
})
