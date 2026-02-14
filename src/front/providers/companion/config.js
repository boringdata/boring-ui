let _baseUrl = ''
let _authToken = ''

export function setCompanionConfig(baseUrl, authToken) {
  const normalized = (baseUrl || '').replace(/\/+$/, '')
  _baseUrl = normalized
  _authToken = authToken || ''
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
