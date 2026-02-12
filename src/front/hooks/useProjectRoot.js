import { useState, useEffect, useCallback, useRef } from 'react'
import { buildApiUrl } from '../utils/apiBase'

/**
 * Fetches and manages the project root path from the backend.
 *
 * Features:
 * - Automatic fetch on mount
 * - Retry logic with exponential backoff (max 6 retries, ~3s total)
 * - Fallback to empty string after max retries to unblock layout restoration
 * - Prevents state overwrites after fallback is applied
 * - Loading state tracking
 * - Error state tracking
 *
 * @returns {Object} { projectRoot, isLoading, error, hasFallback, refetch }
 *
 * @example
 * const { projectRoot, isLoading, hasFallback } = useProjectRoot();
 * if (isLoading) return <Loading />;
 * if (hasFallback) console.warn('Backend unavailable, using fallback');
 * console.log('Project at:', projectRoot);
 */
export function useProjectRoot() {
  const [projectRoot, setProjectRoot] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [hasFallback, setHasFallback] = useState(false)

  const retryCountRef = useRef(0)
  const fallbackAppliedRef = useRef(false)
  const retryTimeoutRef = useRef(null)

  const maxRetries = 6 // ~3 seconds total before initial fallback
  const retryDelay = 500 // milliseconds

  const fetchProjectRoot = useCallback(() => {
    fetch(buildApiUrl('/api/project'))
      .then((r) => {
        if (!r.ok) {
          throw new Error(`HTTP ${r.status}`)
        }
        return r.json()
      })
      .then((data) => {
        const root = data.root || ''
        // Don't update projectRoot after fallback to avoid overwriting project-scoped state
        // (layout/tabs were restored from fallback key; updating root would save to wrong location)
        if (fallbackAppliedRef.current) {
          console.info(
            '[useProjectRoot] Backend available but fallback already applied, refresh to reload project state'
          )
          return
        }
        setProjectRoot(root)
        setIsLoading(false)
        setError(null)
      })
      .catch((err) => {
        retryCountRef.current++
        setError(err)

        if (retryCountRef.current < maxRetries) {
          // Retry on failure - server might not be ready yet
          retryTimeoutRef.current = setTimeout(fetchProjectRoot, retryDelay)
        } else if (!fallbackAppliedRef.current) {
          // After max retries, fall back to empty string to unblock layout restoration
          // We don't continue retrying - user should refresh once backend is available
          console.warn(
            '[useProjectRoot] Failed to fetch project root after retries, using fallback (refresh when backend is available)'
          )
          setProjectRoot('')
          setHasFallback(true)
          fallbackAppliedRef.current = true
          setIsLoading(false)
        }
      })
  }, [])

  // Manual refetch - resets retry count and fallback state
  const refetch = useCallback(() => {
    retryCountRef.current = 0
    fallbackAppliedRef.current = false
    setHasFallback(false)
    setIsLoading(true)
    setError(null)
    fetchProjectRoot()
  }, [fetchProjectRoot])

  useEffect(() => {
    fetchProjectRoot()

    return () => {
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current)
      }
    }
  }, [fetchProjectRoot])

  return {
    projectRoot,
    isLoading,
    error,
    hasFallback,
    refetch,
  }
}
