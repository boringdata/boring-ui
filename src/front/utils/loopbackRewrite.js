const defaultLocation = () => {
  if (typeof window === 'undefined' || !window.location) return null
  return window.location
}

export const isLoopbackHost = (hostname) => (
  hostname === 'localhost'
  || hostname === '127.0.0.1'
  || hostname === '::1'
  || hostname === '[::1]'
)

export const rewriteLoopbackForRemoteClient = (baseUrl, location = defaultLocation()) => {
  if (!baseUrl || !location) return baseUrl

  try {
    const parsed = new URL(baseUrl, location.origin)
    const browserHost = location.hostname
    if (isLoopbackHost(parsed.hostname) && browserHost && !isLoopbackHost(browserHost)) {
      parsed.hostname = browserHost
      return parsed.toString()
    }
  } catch {
    return baseUrl
  }

  return baseUrl
}
