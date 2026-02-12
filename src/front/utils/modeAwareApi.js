/**
 * Mode-aware API URL resolution (bd-1pwb.7.2).
 *
 * In LOCAL mode, legacy endpoints (/api/file, /api/tree, /api/git/*) are
 * available directly. In HOSTED mode, privileged operations must route
 * through the canonical /api/v1/* proxy endpoints.
 *
 * @module utils/modeAwareApi
 */

import { buildApiUrl } from './apiBase'

/**
 * Rewrite a legacy API path to the canonical v1 path for hosted mode.
 *
 * @param {string} path - Original API path (e.g., "/api/file?path=foo.txt")
 * @returns {string} Rewritten path for v1 endpoints
 */
export function rewriteToV1(path) {
  const [pathname, query] = path.split('?')

  const params = new URLSearchParams(query || '')

  // File operations
  if (pathname === '/api/tree') {
    return `/api/v1/files/list${query ? `?${query}` : ''}`
  }
  if (pathname === '/api/file' && !params.has('content')) {
    // GET /api/file?path=X → GET /api/v1/files/read?path=X
    return `/api/v1/files/read${query ? `?${query}` : ''}`
  }

  // Git operations
  if (pathname === '/api/git/status') {
    return '/api/v1/git/status'
  }
  if (pathname === '/api/git/diff') {
    return `/api/v1/git/diff${query ? `?${query}` : ''}`
  }
  if (pathname === '/api/git/show') {
    return `/api/v1/git/show${query ? `?${query}` : ''}`
  }

  // No rewrite needed — return as-is
  return path
}

/**
 * Build a mode-aware API URL.
 *
 * @param {string} path - API path (e.g., "/api/file?path=foo.txt")
 * @param {string} mode - "local" or "hosted"
 * @returns {string} Full URL with mode-appropriate path
 */
export function buildModeAwareUrl(path, mode) {
  if (mode === 'hosted') {
    return buildApiUrl(rewriteToV1(path))
  }
  return buildApiUrl(path)
}
