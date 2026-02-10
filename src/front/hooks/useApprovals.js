/**
 * Approval polling and decision handling hook.
 *
 * Polls /api/approval/pending at 1s interval, filters dismissed approvals,
 * and provides a decision handler that dismisses + closes review panels.
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { buildApiUrl } from '../utils/apiBase'

/**
 * @param {Object} options
 * @param {Object|null} options.dockApi - Dockview API for closing review panels
 * @param {number} [options.pollInterval=1000] - Polling interval in ms
 * @returns {{ approvals: Array, approvalsLoaded: boolean, handleDecision: Function }}
 */
export function useApprovals({ dockApi, pollInterval = 1000 } = {}) {
  const [approvals, setApprovals] = useState([])
  const [approvalsLoaded, setApprovalsLoaded] = useState(false)
  const dismissedRef = useRef(new Set())

  useEffect(() => {
    let isActive = true

    const fetchApprovals = () => {
      fetch(buildApiUrl('/api/approval/pending'))
        .then((r) => r.json())
        .then((data) => {
          if (!isActive) return
          const requests = Array.isArray(data.requests) ? data.requests : []
          const filtered = requests.filter(
            (req) => !dismissedRef.current.has(req.id),
          )
          setApprovals(filtered)
          setApprovalsLoaded(true)
        })
        .catch(() => {})
    }

    fetchApprovals()
    const interval = setInterval(fetchApprovals, pollInterval)

    return () => {
      isActive = false
      clearInterval(interval)
    }
  }, [pollInterval])

  const handleDecision = useCallback(
    async (requestId, decision, reason) => {
      if (requestId) {
        dismissedRef.current.add(requestId)
        setApprovals((prev) => prev.filter((req) => req.id !== requestId))
        if (dockApi) {
          const panel = dockApi.getPanel(`review-${requestId}`)
          if (panel) {
            panel.api.close()
          }
        }
      } else {
        setApprovals([])
      }
      try {
        await fetch(buildApiUrl('/api/approval/decision'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ request_id: requestId, decision, reason }),
        })
      } catch {
        // Ignore decision errors; UI already dismissed.
      }
    },
    [dockApi],
  )

  return { approvals, approvalsLoaded, handleDecision }
}
