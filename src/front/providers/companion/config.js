let _baseUrl = ''
let _authToken = ''

export function setCompanionConfig(baseUrl, authToken) {
  let normalized = String(baseUrl || '').trim()
  if (normalized.startsWith('/') && typeof window !== 'undefined') {
    normalized = `${window.location.origin}${normalized}`
  }
  normalized = normalized.replace(/\/+$/, '')
  _baseUrl = normalized
  _authToken = String(authToken || '').trim()
}

export function getCompanionBaseUrl() {
  return _baseUrl
}

export function getCompanionAuthToken() {
  return _authToken
}

export function getAuthHeaders() {
  if (!_authToken) return {}
  return { Authorization: `Bearer ${_authToken}` }
}
