const normalizeBaseUrl = (serviceUrl) => String(serviceUrl || '').trim().replace(/\/+$/, '')

export const createPiRoutes = (serviceUrl) => {
  const baseUrl = normalizeBaseUrl(serviceUrl)
  const apiBase = baseUrl ? `${baseUrl}/api/v1/agent/pi` : '/api/v1/agent/pi'

  return {
    // "Configured" means a PI service URL was explicitly provided (remote backend mode).
    // Routes still point at canonical same-origin endpoints when baseUrl is missing.
    isConfigured: Boolean(baseUrl),
    sessions: () => `${apiBase}/sessions`,
    history: (sessionId) => `${apiBase}/sessions/${encodeURIComponent(sessionId)}/history`,
    createSession: () => `${apiBase}/sessions/create`,
    stream: (sessionId) => `${apiBase}/sessions/${encodeURIComponent(sessionId)}/stream`,
  }
}
