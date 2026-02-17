import { describe, expect, it } from 'vitest'
import { createPiRoutes } from './routes'

describe('createPiRoutes', () => {
  it('builds canonical PI backend URLs from service base URL', () => {
    const routes = createPiRoutes('http://localhost:9100/')

    expect(routes.isConfigured).toBe(true)
    expect(routes.sessions()).toBe('http://localhost:9100/api/sessions')
    expect(routes.history('session/1')).toBe('http://localhost:9100/api/sessions/session%2F1/history')
    expect(routes.createSession()).toBe('http://localhost:9100/api/sessions/create')
    expect(routes.stream('abc')).toBe('http://localhost:9100/api/sessions/abc/stream')
  })

  it('reports unconfigured routes when service URL is missing', () => {
    const routes = createPiRoutes('')

    expect(routes.isConfigured).toBe(false)
    expect(routes.sessions()).toBe('/sessions')
  })
})
