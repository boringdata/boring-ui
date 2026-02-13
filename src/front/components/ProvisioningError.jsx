/**
 * Provisioning error detail and retry UX component.
 *
 * Bead: bd-223o.14.4 (H4)
 *
 * Shows runtime failure details (error code, detail, attempt count) and
 * an explicit Retry action. Consumed by OnboardingStateGate in the
 * WORKSPACE_SELECTED_ERROR state.
 *
 * Error codes come from the backend provisioning state machine:
 *   STEP_TIMEOUT         — step exceeded its time limit
 *   ARTIFACT_CHECKSUM_MISMATCH — bundle integrity failure
 *   <custom>             — any other error code from the runtime
 */

import { AlertTriangle, Loader2, RefreshCw, ExternalLink } from 'lucide-react'
import { useState, useCallback } from 'react'

// ── Error code labels ────────────────────────────────────────────────

const ERROR_CODE_LABELS = {
  STEP_TIMEOUT: 'Provisioning step timed out',
  ARTIFACT_CHECKSUM_MISMATCH: 'Bundle integrity check failed',
  provision_failed: 'Provisioning failed',
  runtime_status_unavailable: 'Runtime status unavailable',
  health_check_failed: 'Health check failed',
  sandbox_creation_failed: 'Sandbox creation failed',
}

const ERROR_CODE_GUIDANCE = {
  STEP_TIMEOUT: 'A provisioning step exceeded its time limit. Retry usually resolves transient infrastructure delays.',
  ARTIFACT_CHECKSUM_MISMATCH: 'The release artifact failed integrity verification. If this persists, the release may need to be republished.',
  health_check_failed: 'The runtime started but failed its health check. Retry to re-provision from scratch.',
  runtime_status_unavailable: 'Could not reach the runtime status endpoint. This may be a transient network issue.',
}

const getErrorLabel = (code) => ERROR_CODE_LABELS[code] || code || 'Unknown error'
const getErrorGuidance = (code) => ERROR_CODE_GUIDANCE[code] || null

// ── Component ────────────────────────────────────────────────────────

export default function ProvisioningError({
  errorCode,
  errorDetail,
  attempt,
  workspaceName,
  onRetry,
}) {
  const [retrying, setRetrying] = useState(false)
  const [retryResult, setRetryResult] = useState(null)

  const handleRetry = useCallback(async () => {
    if (retrying || !onRetry) return
    setRetrying(true)
    setRetryResult(null)
    try {
      const result = await onRetry()
      if (result && !result.ok) {
        setRetryResult({ ok: false, reason: result.reason || 'retry_failed' })
      }
    } catch {
      setRetryResult({ ok: false, reason: 'retry_exception' })
    } finally {
      setRetrying(false)
    }
  }, [retrying, onRetry])

  const label = getErrorLabel(errorCode)
  const guidance = getErrorGuidance(errorCode)

  return (
    <div className="prov-error" data-testid="provisioning-error">
      <div className="prov-error-icon">
        <AlertTriangle size={24} />
      </div>

      <div className="prov-error-content">
        <h3 className="prov-error-title" data-testid="prov-error-title">
          {label}
        </h3>

        {errorCode && (
          <div className="prov-error-code" data-testid="prov-error-code">
            <span className="prov-error-code-label">Code:</span>
            <code>{errorCode}</code>
          </div>
        )}

        {errorDetail && (
          <p className="prov-error-detail" data-testid="prov-error-detail">
            {errorDetail}
          </p>
        )}

        {guidance && (
          <p className="prov-error-guidance" data-testid="prov-error-guidance">
            {guidance}
          </p>
        )}

        {workspaceName && (
          <div className="prov-error-meta" data-testid="prov-error-workspace">
            Workspace: {workspaceName}
          </div>
        )}

        {attempt > 1 && (
          <div className="prov-error-meta" data-testid="prov-error-attempt">
            Attempt: {attempt}
          </div>
        )}
      </div>

      <div className="prov-error-actions">
        <button
          type="button"
          className="prov-error-retry-btn"
          onClick={handleRetry}
          disabled={retrying}
          data-testid="prov-retry-btn"
        >
          {retrying ? (
            <Loader2 size={16} className="prov-spin" />
          ) : (
            <RefreshCw size={16} />
          )}
          <span>{retrying ? 'Retrying…' : 'Retry provisioning'}</span>
        </button>

        {retryResult && !retryResult.ok && (
          <div className="prov-error-retry-failed" data-testid="prov-retry-failed">
            Retry failed: {retryResult.reason}
          </div>
        )}
      </div>
    </div>
  )
}
