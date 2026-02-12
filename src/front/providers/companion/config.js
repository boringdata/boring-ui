/**
 * Companion configuration for Direct Connect.
 *
 * The adapter sets these values before the upstream App mounts.
 * Upstream api.ts and ws.ts read from here instead of using
 * window.location or hardcoded paths.
 */

let _baseUrl = ''
let _authToken = ''

export function setCompanionConfig(baseUrl, authToken) {
  _baseUrl = baseUrl || ''
  _authToken = authToken || ''
}

export function getCompanionBaseUrl() {
  return _baseUrl
}

export function getCompanionAuthToken() {
  return _authToken
}

/**
 * Build fetch init with Authorization header.
 */
export function getAuthHeaders() {
  if (!_authToken) return {}
  return { Authorization: `Bearer ${_authToken}` }
}
