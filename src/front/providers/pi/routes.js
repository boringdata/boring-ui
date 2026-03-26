const normalizeBaseUrl = (serviceUrl) => String(serviceUrl || '').trim().replace(/\/+$/, '')

export const createPiRoutes = (serviceUrl) => {
  const baseUrl = normalizeBaseUrl(serviceUrl)
  const apiBase = baseUrl ? `${baseUrl}/api/v1/agent/pi` : '/api/v1/agent/pi'
  const sessionsPath = (workspaceId = '') => (
    workspaceId
      ? `${apiBase}/sessions?workspace_id=${encodeURIComponent(workspaceId)}`
      : `${apiBase}/sessions`
  )

  return {
    // "Configured" means a PI service URL was explicitly provided (remote backend mode).
    // Routes still point at canonical same-origin endpoints when baseUrl is missing.
    isConfigured: Boolean(baseUrl),
    sessions: sessionsPath,
    history: (sessionId) => `${apiBase}/sessions/${encodeURIComponent(sessionId)}/history`,
    createSession: () => `${apiBase}/sessions/create`,
    stream: (sessionId) => `${apiBase}/sessions/${encodeURIComponent(sessionId)}/stream`,
  }
}
