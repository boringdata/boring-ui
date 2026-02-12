/**
 * useApiMode hook — provides mode-aware API fetch for privileged operations (bd-1pwb.7.2).
 *
 * Components call `apiFetch(path, init)` instead of `fetch(buildApiUrl(path), init)`.
 * In LOCAL mode, paths pass through unchanged. In HOSTED mode, privileged paths
 * are rewritten to canonical /api/v1/* proxy endpoints.
 *
 * @module hooks/useApiMode
 */

import { useCallback } from 'react'
import { useCapabilitiesContext } from '../components/CapabilityGate'
import { buildModeAwareUrl } from '../utils/modeAwareApi'
import { appendWsToken } from '../utils/wsAuth'

/**
 * Hook providing mode-aware API fetch and WebSocket auth.
 *
 * @returns {{
 *   mode: string,
 *   apiFetch: (path: string, init?: RequestInit) => Promise<Response>,
 *   buildUrl: (path: string) => string,
 *   buildWsUrlWithAuth: (url: string) => string,
 * }}
 */
export function useApiMode() {
  const capabilities = useCapabilitiesContext()
  const mode = capabilities?.mode || 'local'
  const wsToken = capabilities?.wsToken || null

  const buildUrl = useCallback(
    (path) => buildModeAwareUrl(path, mode),
    [mode],
  )

  const apiFetch = useCallback(
    (path, init) => fetch(buildUrl(path), init),
    [buildUrl],
  )

  /** Append auth token to a WebSocket URL when in hosted mode. */
  const buildWsUrlWithAuth = useCallback(
    (url) => (mode === 'hosted' ? appendWsToken(url, wsToken) : url),
    [mode, wsToken],
  )

  return { mode, apiFetch, buildUrl, buildWsUrlWithAuth }
}

export default useApiMode
