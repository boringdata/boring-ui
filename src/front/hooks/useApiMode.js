/**
 * useApiMode hook — provides canonical API fetch + hosted auth attachment.
 *
 * Components call `apiFetch(path, init)` instead of raw `fetch`.
 * Callers should provide canonical paths directly (e.g. `/api/v1/files/read?...`).
 *
 * @module hooks/useApiMode
 */

import { useCallback } from 'react'
import { useCapabilitiesContext } from '../components/CapabilityGate'
import { buildApiUrl } from '../utils/apiBase'
import { appendWsToken } from '../utils/wsAuth'
import { apiFetch as sharedApiFetch, setApiMode } from '../utils/apiFetch'

/**
 * Hook providing mode-aware API fetch and WebSocket auth.
 *
 * @returns {{
 *   mode: string,
 *   apiFetch: (path: string, init?: RequestInit) => Promise<Response>,
 *   buildUrl: (path: string, method?: string) => string,
 *   buildWsUrlWithAuth: (url: string) => string,
 * }}
 */
export function useApiMode() {
  const capabilities = useCapabilitiesContext()
  const mode = capabilities?.mode || 'local'
  const wsToken = capabilities?.wsToken || null
  setApiMode(mode)

  const buildUrl = useCallback(
    (path) => buildApiUrl(path),
    [],
  )

  const apiFetch = useCallback(
    (path, init) => sharedApiFetch(path, init, mode),
    [mode],
  )

  /** Append auth token to a WebSocket URL when in hosted mode. */
  const buildWsUrlWithAuth = useCallback(
    (url) => (mode === 'hosted' ? appendWsToken(url, wsToken) : url),
    [mode, wsToken],
  )

  return { mode, apiFetch, buildUrl, buildWsUrlWithAuth }
}

export default useApiMode
