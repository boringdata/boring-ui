import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createApp } from '../app.js'

describe('Workspace HTTP routes', () => {
  // Test via Fastify inject (no real DB needed for route-level tests)

  describe('POST /api/v1/workspaces', () => {
    it('returns 401 without session cookie', async () => {
      const app = createApp()
      const res = await app.inject({
        method: 'POST',
        url: '/api/v1/workspaces',
        payload: { name: 'Test Workspace' },
      })
      expect(res.statusCode).toBe(401)
      await app.close()
    })
  })

  describe('GET /api/v1/workspaces', () => {
    it('returns 401 without session cookie', async () => {
      const app = createApp()
      const res = await app.inject({
        method: 'GET',
        url: '/api/v1/workspaces',
      })
      expect(res.statusCode).toBe(401)
      await app.close()
    })
  })

  describe('GET /api/v1/workspaces/:id/runtime', () => {
    it('returns 401 without session cookie', async () => {
      const app = createApp()
      const res = await app.inject({
        method: 'GET',
        url: '/api/v1/workspaces/00000000-0000-0000-0000-000000000001/runtime',
      })
      expect(res.statusCode).toBe(401)
      await app.close()
    })
  })

  describe('GET /api/v1/workspaces/:id/settings', () => {
    it('returns 401 without session cookie', async () => {
      const app = createApp()
      const res = await app.inject({
        method: 'GET',
        url: '/api/v1/workspaces/00000000-0000-0000-0000-000000000001/settings',
      })
      expect(res.statusCode).toBe(401)
      await app.close()
    })
  })

  describe('PUT /api/v1/workspaces/:id/settings', () => {
    it('returns 401 without session cookie', async () => {
      const app = createApp()
      const res = await app.inject({
        method: 'PUT',
        url: '/api/v1/workspaces/00000000-0000-0000-0000-000000000001/settings',
        payload: { api_key: 'test' },
      })
      expect(res.statusCode).toBe(401)
      await app.close()
    })
  })
})

describe('WorkspaceService interface', () => {
  it('exports WorkspaceService type (interface only, no factory)', async () => {
    const mod = await import('../services/workspaces.js')
    // Factory was removed — only the interface type remains
    expect((mod as any).createWorkspaceService).toBeUndefined()
  })
})

describe('Membership helper', () => {
  it('exports requireMembership function', async () => {
    const mod = await import('../workspace/membership.js')
    expect(typeof mod.requireMembership).toBe('function')
  })

  it('exports MemberRole type values', async () => {
    const mod = await import('../workspace/membership.js')
    expect(mod.MEMBER_ROLES).toContain('owner')
    expect(mod.MEMBER_ROLES).toContain('editor')
    expect(mod.MEMBER_ROLES).toContain('viewer')
  })
})

describe('Workspace path helpers', () => {
  it('validatePath joins root + relative path safely', async () => {
    const { validatePath } = await import('../workspace/paths.js')
    const result = validatePath('/workspaces', 'abc-123')
    expect(result).toMatch(/workspaces.*abc-123/)
  })
})
