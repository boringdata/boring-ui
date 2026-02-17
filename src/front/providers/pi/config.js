import { rewriteLoopbackForRemoteClient } from '../../utils/loopbackRewrite'

const normalizeBase = (value) => String(value || '').trim().replace(/\/+$/, '')

export function resolvePiServiceUrl(rawUrl) {
  const normalized = normalizeBase(rawUrl)
  if (!normalized) return ''

  let absolute = normalized
  if (absolute.startsWith('/') && typeof window !== 'undefined') {
    absolute = `${window.location.origin}${absolute}`
  }

  return rewriteLoopbackForRemoteClient(absolute)
}

export function isPiBackendMode(capabilities) {
  const serviceMode = String(capabilities?.services?.pi?.mode || '').toLowerCase()
  if (serviceMode === 'backend') return true
  return Boolean(resolvePiServiceUrl(import.meta.env.VITE_PI_SERVICE_URL || ''))
}

export function getPiServiceUrl(capabilities) {
  const fromCapabilities = resolvePiServiceUrl(capabilities?.services?.pi?.url || '')
  if (fromCapabilities) return fromCapabilities
  return resolvePiServiceUrl(import.meta.env.VITE_PI_SERVICE_URL || '')
}
