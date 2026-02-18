const normalizeBaseUrl = (serviceUrl) => String(serviceUrl || '').replace(/\/+$/, '')

export const createPiRoutes = (serviceUrl) => {
  const baseUrl = normalizeBaseUrl(serviceUrl)
  const apiBase = baseUrl ? `${baseUrl}/api/v1/agent/pi` : ''

  return {
    isConfigured: Boolean(apiBase),
    sessions: () => `${apiBase}/sessions`,
    history: (sessionId) => `${apiBase}/sessions/${encodeURIComponent(sessionId)}/history`,
    createSession: () => `${apiBase}/sessions/create`,
    stream: (sessionId) => `${apiBase}/sessions/${encodeURIComponent(sessionId)}/stream`,
  }
}
