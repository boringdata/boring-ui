import { describe, expect, it } from 'vitest'
import { createPiRoutes } from './routes'

describe('createPiRoutes', () => {
  it('builds canonical PI backend URLs from service base URL', () => {
    const routes = createPiRoutes('http://localhost:9100/')

    expect(routes.isConfigured).toBe(true)
    expect(routes.sessions()).toBe('http://localhost:9100/api/v1/agent/pi/sessions')
    expect(routes.history('session/1')).toBe('http://localhost:9100/api/v1/agent/pi/sessions/session%2F1/history')
    expect(routes.createSession()).toBe('http://localhost:9100/api/v1/agent/pi/sessions/create')
    expect(routes.stream('abc')).toBe('http://localhost:9100/api/v1/agent/pi/sessions/abc/stream')
  })

  it('reports unconfigured routes when service URL is missing', () => {
    const routes = createPiRoutes('')

    expect(routes.isConfigured).toBe(false)
    expect(routes.sessions()).toBe('/sessions')
    expect(routes.history('abc')).toBe('/sessions/abc/history')
    expect(routes.createSession()).toBe('/sessions/create')
    expect(routes.stream('abc')).toBe('/sessions/abc/stream')
  })
})
