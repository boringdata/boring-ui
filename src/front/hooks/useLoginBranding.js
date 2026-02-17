/**
 * Hook to fetch and resolve login branding from the app-config endpoint.
 *
 * Bead: bd-223o.14.5 (H5)
 *
 * Fetches GET /api/v1/app-config and resolves branding using the
 * three-level precedence chain:
 *   1. Workspace runtime config (login_branding) — if workspace context
 *   2. App default config (name, logo from app-config)
 *   3. Hardcoded frontend fallback (from appConfig.js defaults)
 *
 * Returns { name, logo, loading } for consumption by OnboardingStateGate.
 */

import { useState, useEffect, useCallback } from 'react'
import { buildApiUrl } from '../utils/apiBase'
import { getConfig, getDefaultConfig } from '../config/appConfig'

const FALLBACK = {
  name: 'Boring UI',
  logo: '',
}

/**
 * Fetch and resolve login page branding.
 *
 * @param {{ workspaceBranding?: { name?: string, logo?: string } }} [options]
 * @returns {{ name: string, logo: string, source: string, loading: boolean }}
 */
export default function useLoginBranding(options = {}) {
  const { workspaceBranding } = options
  const [appConfig, setAppConfig] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    const fetchConfig = async () => {
      try {
        const response = await fetch(buildApiUrl('/api/v1/app-config'))
        if (response.ok) {
          const data = await response.json()
          if (!cancelled) setAppConfig(data)
        }
      } catch {
        // App-config unavailable — fall back to local config.
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    fetchConfig()
    return () => { cancelled = true }
  }, [])

  // Resolve branding using precedence chain.
  const resolved = resolveClientBranding(workspaceBranding, appConfig)

  return { ...resolved, loading }
}

/**
 * Client-side branding resolution (mirrors backend resolve_login_branding).
 *
 * Precedence: workspace → app-config → local config → hardcoded fallback.
 */
function resolveClientBranding(workspaceBranding, appConfig) {
  // Level 1: Workspace branding overrides.
  const wsName = workspaceBranding?.name || ''
  const wsLogo = workspaceBranding?.logo || ''

  // Level 2: App-config from backend.
  const acName = appConfig?.name || ''
  const acLogo = appConfig?.logo || ''

  // Level 3: Local frontend config.
  const localConfig = getConfig() || getDefaultConfig()
  const lcName = localConfig?.branding?.name || ''
  const lcLogo = localConfig?.branding?.logo || ''

  // Resolve each field independently — first non-empty wins.
  const name = wsName || acName || lcName || FALLBACK.name
  const logo = wsLogo || acLogo || lcLogo || FALLBACK.logo

  // Determine source for debugging/testing.
  let source = 'default'
  if (wsName || wsLogo) source = 'workspace'
  else if (acName || acLogo) source = 'app'
  else if (lcName || lcLogo) source = 'local'

  return { name, logo, source }
}

// Export for testing.
export { resolveClientBranding }
