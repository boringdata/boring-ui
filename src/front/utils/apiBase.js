const normalizeBase = (value) => (value ? value.replace(/\/$/, '') : '')

const isDevPort = (port) => {
  const devPorts = new Set(['3000', '3001', '4173', '4174', '5173', '5174', '5175', '5176'])
  return devPorts.has(port)
}

const resolveApiBase = () => {
  const envUrl = import.meta.env.VITE_API_URL || ''
  if (envUrl) return normalizeBase(envUrl)

  if (typeof window !== 'undefined' && window.location) {
    const { port, origin } = window.location
    // In dev, prefer same-origin requests so Vite proxy handles /api and /ws.
    // This avoids hard-coding :8000 and eliminates cross-origin failures when
    // frontend is accessed remotely.
    if (port && isDevPort(port)) return normalizeBase(origin)
    if (origin) return origin
  }

  return 'http://localhost:8000'
}

export const getApiBase = () => resolveApiBase()

export const buildApiUrl = (path) => `${getApiBase()}${path}`

export const getWsBase = () => {
  const envWsUrl = import.meta.env.VITE_WS_URL || ''
  if (envWsUrl) return normalizeBase(envWsUrl)

  if (typeof window !== 'undefined' && window.location) {
    const { protocol, hostname, port } = window.location
    if (port && isDevPort(port)) {
      const wsProtocol = protocol === 'https:' ? 'wss' : 'ws'
      return `${wsProtocol}://${hostname}:8000`
    }
  }

  const apiBase = getApiBase()
  const url = new URL(apiBase)
  const protocol = url.protocol === 'https:' ? 'wss' : 'ws'
  return `${protocol}://${url.host}`
}
