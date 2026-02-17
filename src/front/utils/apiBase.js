const normalizeBase = (value) => (value ? value.replace(/\/$/, '') : '')

const isDevPort = (port) => {
  const devPorts = new Set(['3000', '3001', '4173', '4174', '5173', '5174', '5175', '5176', '5180', '5190'])
  return devPorts.has(port)
}

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
      return normalizeBase(parsed.toString())
    }
  } catch {
    return baseUrl
  }

  return baseUrl
}

const resolveApiBase = () => {
  const envUrl = import.meta.env.VITE_API_URL || ''
  if (envUrl) return rewriteLoopbackForRemoteClient(normalizeBase(envUrl))

  if (typeof window !== 'undefined' && window.location) {
    const { protocol, hostname, port, origin } = window.location
    if (port && isDevPort(port)) {
      return `${protocol}//${hostname}:8000`
    }
    if (origin) return origin
  }

  return 'http://localhost:8000'
}

export const getApiBase = () => resolveApiBase()

export const buildApiUrl = (path) => `${getApiBase()}${path}`

export const getWsBase = () => {
  const apiBase = getApiBase()
  const url = new URL(apiBase)
  const protocol = url.protocol === 'https:' ? 'wss' : 'ws'
  return `${protocol}://${url.host}`
}

export const __apiBaseTestUtils = {
  isDevPort,
  isLoopbackHost,
  rewriteLoopbackForRemoteClient,
}
