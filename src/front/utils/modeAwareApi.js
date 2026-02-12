/**
 * Mode-aware API helpers.
 *
 * Frontend callers should target canonical `/api/v1/*` endpoints directly.
 * This module keeps compatibility helpers as no-ops and provides response
 * adapters where UI state still expects legacy field names.
 *
 * @module utils/modeAwareApi
 */

import { buildApiUrl } from './apiBase'

/**
 * Compatibility no-op. Callers should already pass canonical paths.
 *
 * @param {string} path - Original API path (e.g., "/api/file?path=foo.txt")
 * @param {string} [method='GET'] - HTTP method
 * @returns {string} Rewritten path for v1 endpoints
 */
export function rewriteToV1(path, method = 'GET') {
  void method
  return path
}

/**
 * Compatibility no-op. Write calls should already target `/api/v1/files/write`.
 *
 * @param {string} path - API path
 * @param {RequestInit} [init] - fetch init options
 * @returns {{ url: string, init: RequestInit } | null} Transformed request, or null if no transform needed
 */
export function rewriteWriteOp(path, init) {
  void path
  void init
  return null
}

/**
 * Build a mode-aware API URL.
 *
 * @param {string} path - API path (e.g., "/api/file?path=foo.txt")
 * @param {string} mode - "local" or "hosted"
 * @param {string} [method='GET'] - HTTP method
 * @returns {string} Full URL with mode-appropriate path
 */
export function buildModeAwareUrl(path, mode, method = 'GET') {
  void mode
  void method
  return buildApiUrl(path)
}

// ── Response adapters ──────────────────────────────────────────────────
// V1 response shapes differ from legacy. These pure functions normalize
// v1 responses to the shapes components already expect.

/**
 * Adapt a v1 ListFilesResponse to the legacy tree shape.
 *
 * V1:     { path: ".", files: [{name, type, size}] }
 * Legacy: { entries: [{path, name, is_dir, size}] }
 *
 * @param {Object} data - Response data (may be v1 or legacy)
 * @param {string} dirPath - The directory path that was listed
 * @returns {Object} Normalized response with `entries` array
 */
export function adaptListFiles(data, dirPath) {
  // Already legacy shape
  if (Array.isArray(data.entries)) return data

  // V1 shape — transform
  if (Array.isArray(data.files)) {
    const basePath = dirPath === '.' ? '' : dirPath
    return {
      entries: data.files.map((f) => ({
        name: f.name,
        path: basePath ? `${basePath}/${f.name}` : f.name,
        is_dir: f.type === 'dir',
        size: f.size ?? null,
      })),
    }
  }

  // Unknown shape — return empty
  return { entries: [] }
}

/**
 * Adapt a v1 GitStatusResponse to the legacy shape.
 *
 * V1:     { is_repo: bool, files: {...} }
 * Legacy: { available: bool, files: {...} }
 *
 * @param {Object} data - Response data (may be v1 or legacy)
 * @returns {Object} Normalized response with `available` field
 */
export function adaptGitStatus(data) {
  // Already has legacy `available` field
  if ('available' in data) return data

  // V1 shape — add `available` from `is_repo`
  return {
    ...data,
    available: data.is_repo ?? false,
  }
}
