/**
 * Shared API fetch wrapper for browser-side /api/* calls.
 *
 * Provides:
 * - Canonical `/api/v1/*` URL support
 * - Hosted Authorization header injection from authStore
 */

import { buildApiUrl } from './apiBase'
import { getAuthToken } from './authStore'

let _apiMode = 'local'

export const setApiMode = (mode) => {
  _apiMode = mode === 'hosted' ? 'hosted' : 'local'
}

export const getApiMode = () => _apiMode

export const apiFetch = (path, init = undefined, modeOverride = undefined) => {
  const mode = modeOverride || _apiMode || 'local'

  if (typeof path !== 'string' || !path.startsWith('/api/')) {
    return fetch(path, init)
  }
  const url = buildApiUrl(path)
  if (mode !== 'hosted') {
    return fetch(url, init)
  }

  const token = getAuthToken()
  if (!token) {
    return fetch(url, init)
  }

  const headers = { ...(init?.headers || {}), Authorization: `Bearer ${token}` }
  return fetch(url, { ...init, headers })
}

export default apiFetch
