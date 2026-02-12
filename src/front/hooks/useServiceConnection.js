/**
 * useServiceConnection hook — provides direct-connect service info
 * fetched from /api/capabilities.
 *
 * Tokens are stored in React state only (never localStorage).
 * Provides helpers for auth headers and query-param tokens.
 *
 * @module hooks/useServiceConnection
 */

import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { apiFetch } from '../utils/apiFetch'

const MAX_RETRIES = 3
const INITIAL_BACKOFF_MS = 500

/**
 * @typedef {Object} ServiceInfo
 * @property {string} url     - Direct-connect base URL
 * @property {string} token   - Bearer token for REST requests
 * @property {string} qpToken - Short-lived token for SSE/WS query params
 * @property {string} protocol - "rest+sse" | "rest+ws"
 */

/**
 * Hook that fetches service connection info from capabilities
 * and provides auth helpers for direct-connect adapters.
 *
 * @returns {{
 *   services: Object<string, ServiceInfo>|null,
 *   isLoading: boolean,
 *   error: Error|null,
 *   refreshTokens: () => Promise<void>,
 *   getAuthHeaders: (serviceName: string, extra?: Object) => Object,
 *   getQpToken: (serviceName: string) => string|null,
 *   getServiceUrl: (serviceName: string) => string|null,
 * }}
 */
export function useServiceConnection() {
  const [services, setServices] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const retryCount = useRef(0)
  const mounted = useRef(true)

  const fetchServices = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)

      const response = await apiFetch('/api/capabilities')
      if (!response.ok) {
        throw new Error(`Capabilities fetch failed: ${response.status}`)
      }

      const data = await response.json()
      const newServices = data.services || null
      if (mounted.current) {
        setServices(newServices)
        retryCount.current = 0
      }
      return newServices
    } catch (err) {
      console.error('[ServiceConnection] Failed to fetch:', err)
      if (mounted.current) {
        setError(err)
      }
      return null
    } finally {
      if (mounted.current) {
        setIsLoading(false)
      }
    }
  }, [])

  // Fetch on mount, clear on unmount
  useEffect(() => {
    mounted.current = true
    fetchServices()
    return () => {
      mounted.current = false
      setServices(null)
    }
  }, [fetchServices])

  /**
   * Refresh tokens by re-fetching capabilities.
   * Call this on 401 responses. Implements exponential backoff.
   *
   * @returns {Promise<Object|null>} Fresh services map or null on failure
   */
  const refreshTokens = useCallback(async () => {
    if (retryCount.current >= MAX_RETRIES) {
      console.warn('[ServiceConnection] Max retries reached, not refreshing')
      return null
    }
    const delay = INITIAL_BACKOFF_MS * Math.pow(2, retryCount.current)
    retryCount.current += 1
    await new Promise((r) => setTimeout(r, delay))
    return await fetchServices()
  }, [fetchServices])

  /**
   * Build auth headers for a service. Merges with any extra headers.
   *
   * @param {string} serviceName - e.g. "sandbox"
   * @param {Object} [extra={}]  - Additional headers to include
   * @returns {Object} Headers object with Authorization if available
   */
  const getAuthHeaders = useCallback(
    (serviceName, extra = {}) => {
      const headers = { ...extra }
      const token = services?.[serviceName]?.token
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }
      return headers
    },
    [services],
  )

  /**
   * Get the short-lived query-param token for SSE/WS connections.
   *
   * @param {string} serviceName
   * @returns {string|null}
   */
  const getQpToken = useCallback(
    (serviceName) => services?.[serviceName]?.qpToken ?? null,
    [services],
  )

  /**
   * Get the direct-connect base URL for a service.
   *
   * @param {string} serviceName
   * @returns {string|null}
   */
  const getServiceUrl = useCallback(
    (serviceName) => services?.[serviceName]?.url ?? null,
    [services],
  )

  /**
   * Fetch with automatic 401 retry. On 401, refreshes tokens and
   * retries the request once with the fresh token (not the stale closure).
   *
   * @param {string} serviceName - Service to auth against
   * @param {string} url         - Request URL
   * @param {RequestInit} [init] - Fetch options (headers merged with auth)
   * @returns {Promise<Response>}
   */
  const fetchWithRetry = useCallback(
    async (serviceName, url, init = {}) => {
      const { headers: extraHeaders, ...restInit } = init
      const headers = getAuthHeaders(serviceName, extraHeaders || {})
      const response = await fetch(url, { ...restInit, headers })

      if (response.status !== 401) return response

      // Refresh and retry once with fresh token from the returned data
      const freshServices = await refreshTokens()
      if (!freshServices) return response

      const freshToken = freshServices[serviceName]?.token
      const retryHeaders = { ...(extraHeaders || {}) }
      if (freshToken) {
        retryHeaders['Authorization'] = `Bearer ${freshToken}`
      }
      return fetch(url, { ...restInit, headers: retryHeaders })
    },
    [getAuthHeaders, refreshTokens],
  )

  return useMemo(
    () => ({
      services,
      isLoading,
      error,
      refreshTokens,
      getAuthHeaders,
      getQpToken,
      getServiceUrl,
      fetchWithRetry,
    }),
    [services, isLoading, error, refreshTokens, getAuthHeaders, getQpToken, getServiceUrl, fetchWithRetry],
  )
}

export default useServiceConnection
