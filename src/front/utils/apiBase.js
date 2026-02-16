const normalizeBase = (value) => (value ? value.replace(/\/$/, '') : '')

const isDevPort = (port) => {
  const portNumber = Number.parseInt(port, 10)
  if (!Number.isFinite(portNumber)) return false
  return (
    (portNumber >= 3000 && portNumber <= 3010)
    || (portNumber >= 4173 && portNumber <= 4179)
    || (portNumber >= 5173 && portNumber <= 5199)
  )
}

const resolveApiBase = () => {
  const envUrl = import.meta.env.VITE_API_URL || ''
  if (envUrl) return normalizeBase(envUrl)

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
