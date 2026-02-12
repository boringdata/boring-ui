import { describe, it, expect } from 'vitest'
import { rewriteToV1, buildModeAwareUrl } from './modeAwareApi'

describe('modeAwareApi', () => {
  describe('rewriteToV1', () => {
    it('rewrites privileged GET routes to canonical /api/v1 routes', () => {
      expect(rewriteToV1('/api/tree?path=.', 'GET')).toBe('/api/v1/files/list?path=.')
      expect(rewriteToV1('/api/file?path=README.md', 'GET')).toBe('/api/v1/files/read?path=README.md')
      expect(rewriteToV1('/api/git/status', 'GET')).toBe('/api/v1/git/status')
      expect(rewriteToV1('/api/git/diff?path=a.txt', 'GET')).toBe('/api/v1/git/diff?path=a.txt')
      expect(rewriteToV1('/api/git/show?path=a.txt', 'GET')).toBe('/api/v1/git/show?path=a.txt')
    })

    it('does not rewrite non-GET /api/file operations', () => {
      expect(rewriteToV1('/api/file?path=README.md', 'PUT')).toBe('/api/file?path=README.md')
      expect(rewriteToV1('/api/file?path=README.md', 'DELETE')).toBe('/api/file?path=README.md')
      expect(rewriteToV1('/api/file?path=README.md', 'POST')).toBe('/api/file?path=README.md')
    })
  })

  describe('buildModeAwareUrl', () => {
    it('rewrites paths in hosted mode and keeps local mode unchanged', () => {
      expect(buildModeAwareUrl('/api/tree?path=.', 'hosted', 'GET')).toMatch(/\/api\/v1\/files\/list\?path=\.$/)
      expect(buildModeAwareUrl('/api/tree?path=.', 'local', 'GET')).toMatch(/\/api\/tree\?path=\.$/)
      expect(buildModeAwareUrl('/api/file?path=x.txt', 'hosted', 'PUT')).toMatch(/\/api\/file\?path=x\.txt$/)
    })
  })
})
