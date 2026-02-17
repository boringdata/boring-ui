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

  it('builds websocket route descriptors without feature-local literals', () => {
    expect(routes.ws.plugins()).toEqual({ path: '/ws/plugins' })
    expect(routes.ws.claudeStream({ session_id: 'abc' })).toEqual({
      path: '/ws/claude-stream',
      query: { session_id: 'abc' },
    })
  })
})
