let _baseUrl = ''
let _authToken = ''

const isLoopbackHost = (hostname) => hostname === 'localhost' || hostname === '127.0.0.1'

const rewriteLoopbackForRemoteClient = (baseUrl, location = typeof window !== 'undefined' ? window.location : null) => {
  if (!baseUrl || !location) {
    return baseUrl
  }

  try {
    const parsed = new URL(baseUrl, location.origin)
    const browserHost = location.hostname
    if (isLoopbackHost(parsed.hostname) && browserHost && !isLoopbackHost(browserHost)) {
      parsed.hostname = browserHost
      return parsed.toString().replace(/\/+$/, '')
    }
  } catch {
    return baseUrl
  }

  return baseUrl
}

export function setCompanionConfig(baseUrl, authToken) {
  let normalized = String(baseUrl || '').trim()
  if (normalized.startsWith('/') && typeof window !== 'undefined') {
    normalized = `${window.location.origin}${normalized}`
  }
  normalized = normalized.replace(/\/+$/, '')
  normalized = rewriteLoopbackForRemoteClient(normalized)
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

export const __companionConfigTestUtils = {
  isLoopbackHost,
  rewriteLoopbackForRemoteClient,
}
