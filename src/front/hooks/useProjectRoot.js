/**
 * Hook to fetch and manage the project root path.
 *
 * Retries on failure (backend may not be ready yet), with fallback
 * to empty string after max retries to unblock layout restoration.
 */

import { useState, useEffect, useRef } from 'react'
import { buildApiUrl } from '../utils/apiBase'

/**
 * Fetch project root from the backend with retry logic.
 *
 * @param {Object} [options]
 * @param {number} [options.maxRetries=6] - Max retry attempts before fallback
 * @param {number} [options.retryDelay=500] - Delay between retries in ms
 * @returns {{ projectRoot: string|null, projectRootRef: React.MutableRefObject<string|null> }}
 *   projectRoot is null until loaded (or fallback applied), then string.
 */
export function useProjectRoot({ maxRetries = 6, retryDelay = 500 } = {}) {
  const [projectRoot, setProjectRoot] = useState(null)
  const projectRootRef = useRef(null)

  useEffect(() => {
    let retryCount = 0
    let fallbackApplied = false

    const fetchProjectRoot = () => {
      fetch(buildApiUrl('/api/project'))
        .then((r) => r.json())
        .then((data) => {
          const root = data.root || ''
          if (fallbackApplied) {
            console.info(
              '[useProjectRoot] Backend available but fallback already applied, refresh to reload project state',
            )
            return
          }
          projectRootRef.current = root
          setProjectRoot(root)
        })
        .catch(() => {
          retryCount++
          if (retryCount < maxRetries) {
            setTimeout(fetchProjectRoot, retryDelay)
          } else if (!fallbackApplied) {
            console.warn(
              '[useProjectRoot] Failed to fetch project root after retries, using fallback',
            )
            projectRootRef.current = ''
            setProjectRoot('')
            fallbackApplied = true
          }
        })
    }

    fetchProjectRoot()
  }, [maxRetries, retryDelay])

  return { projectRoot, projectRootRef }
}
