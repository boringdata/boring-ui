let _baseUrl = ''
let _authToken = ''

export function setCompanionConfig(baseUrl, authToken) {
  const normalized = String(baseUrl || '').replace(/\/+$/, '')
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

