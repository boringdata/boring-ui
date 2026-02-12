/**
 * Approval polling and decision handling.
 *
 * Extracted from App.jsx lines 328-381. Polls /api/approval/pending at
 * 1-second intervals, filters dismissed approvals, and sends decisions.
 */

import { useState, useRef, useEffect, useCallback } from 'react'
import { buildApiUrl } from '../utils/apiBase'

/**
 * Polls for pending approvals and handles decisions.
 *
 * @param {Object} options
 * @param {Object|null} options.dockApi - Dockview API for closing review panels
 * @param {number} [options.pollInterval=1000] - Polling interval in ms
 * @returns {Object} { approvals, approvalsLoaded, handleDecision, dismissedApprovalsRef }
 */
export function useApprovals({ dockApi, pollInterval = 1000 } = {}) {
  const [approvals, setApprovals] = useState([])
  const [approvalsLoaded, setApprovalsLoaded] = useState(false)
  const dismissedApprovalsRef = useRef(new Set())

  // Poll for pending approvals
  useEffect(() => {
    let isActive = true

    const fetchApprovals = () => {
      fetch(buildApiUrl('/api/approval/pending'))
        .then((r) => r.json())
        .then((data) => {
          if (!isActive) return
          const requests = Array.isArray(data.requests) ? data.requests : []
          const filtered = requests.filter(
            (req) => !dismissedApprovalsRef.current.has(req.id),
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

  // Handle approval decision
  const handleDecision = useCallback(
    async (requestId, decision, reason) => {
      if (requestId) {
        dismissedApprovalsRef.current.add(requestId)
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

  return {
    approvals,
    setApprovals,
    approvalsLoaded,
    setApprovalsLoaded,
    handleDecision,
    dismissedApprovalsRef,
  }
}
