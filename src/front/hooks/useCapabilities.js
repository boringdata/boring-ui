/**
 * useCapabilities hook - Fetches and caches backend API capabilities.
 *
 * This hook fetches capabilities from /api/capabilities and provides
 * them to components for feature gating and conditional rendering.
 *
 * @module hooks/useCapabilities
 */

import { useState, useEffect, useCallback } from 'react'
import { buildApiUrl } from '../utils/apiBase'

/**
 * @typedef {Object} Capabilities
 * @property {string} version - API version
 * @property {Object<string, boolean>} features - Feature flags
 * @property {Array<{name: string, prefix: string, enabled: boolean}>} routers - Router info
 */

/**
 * Hook to fetch and cache backend capabilities.
 *
 * @returns {{
 *   capabilities: Capabilities|null,
 *   loading: boolean,
 *   error: Error|null,
 *   refetch: () => Promise<void>
 * }}
 */
export const useCapabilities = () => {
  const [capabilities, setCapabilities] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchCapabilities = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      const response = await fetch(buildApiUrl('/api/capabilities'))
      if (!response.ok) {
        throw new Error(`Failed to fetch capabilities: ${response.status}`)
      }

      const data = await response.json()
      setCapabilities(data)
    } catch (err) {
      console.error('[Capabilities] Failed to fetch:', err)
      setError(err)
      // Set default capabilities on error to prevent blocking
      setCapabilities({
        version: 'unknown',
        features: {},
        routers: [],
      })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchCapabilities()
  }, [fetchCapabilities])

  return {
    capabilities,
    loading,
    error,
    refetch: fetchCapabilities,
  }
}

/**
 * Check if a feature is enabled in capabilities.
 *
 * @param {Capabilities|null} capabilities - Capabilities object
 * @param {string} feature - Feature name to check
 * @returns {boolean}
 */
export const isFeatureEnabled = (capabilities, feature) => {
  return capabilities?.features?.[feature] ?? false
}

/**
 * Check if all required features are enabled.
 *
 * @param {Capabilities|null} capabilities - Capabilities object
 * @param {string[]} features - Feature names to check
 * @returns {boolean}
 */
export const areAllFeaturesEnabled = (capabilities, features) => {
  if (!features || features.length === 0) return true
  return features.every((f) => isFeatureEnabled(capabilities, f))
}

export default useCapabilities
