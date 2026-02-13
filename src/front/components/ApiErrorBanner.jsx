/**
 * Reusable API error banner with actionable messaging and retry.
 *
 * Bead: bd-223o.14.3.1 (H3a)
 *
 * Translates HTTP status codes and backend error codes into
 * user-friendly labels, guidance text, and optional retry action.
 *
 * Props:
 *   error   — { status, label, guidance, detail?, retryable, action }
 *              (output of resolveApiError / resolveFromError)
 *   onRetry — optional callback; shown when error.retryable is true
 *   onDismiss — optional callback to close the banner
 *   onAction  — optional callback for non-retry actions (sign_in, navigate_back, etc.)
 */

import { AlertTriangle, Loader2, LogIn, RefreshCw, X } from 'lucide-react'
import { useState, useCallback } from 'react'

const ACTION_LABELS = {
  sign_in: 'Sign in',
  retry: 'Retry',
  refresh: 'Refresh',
  navigate_back: 'Go back',
  contact_admin: 'Contact admin',
  dismiss: 'Dismiss',
  fix_input: 'Fix input',
  rename: 'Rename',
}

const ACTION_ICONS = {
  sign_in: LogIn,
  retry: RefreshCw,
  refresh: RefreshCw,
}

export default function ApiErrorBanner({ error, onRetry, onDismiss, onAction }) {
  const [retrying, setRetrying] = useState(false)

  const handleRetry = useCallback(async () => {
    if (retrying || !onRetry) return
    setRetrying(true)
    try {
      await onRetry()
    } catch {
      // Retry itself failed — banner stays visible.
    } finally {
      setRetrying(false)
    }
  }, [retrying, onRetry])

  if (!error) return null

  const showRetry = error.retryable && onRetry
  const showAction = error.action && onAction && !showRetry
  const ActionIcon = ACTION_ICONS[error.action] || null
  const actionLabel = ACTION_LABELS[error.action] || error.action

  return (
    <div
      className="api-error-banner"
      role="alert"
      data-testid="api-error-banner"
      data-status={error.status}
    >
      <div className="api-error-banner-icon">
        <AlertTriangle size={16} />
      </div>

      <div className="api-error-banner-content">
        <div className="api-error-banner-label" data-testid="api-error-label">
          {error.label}
        </div>
        <div className="api-error-banner-guidance" data-testid="api-error-guidance">
          {error.guidance}
        </div>
        {error.detail && (
          <div className="api-error-banner-detail" data-testid="api-error-detail">
            {error.detail}
          </div>
        )}
      </div>

      <div className="api-error-banner-actions">
        {showRetry && (
          <button
            type="button"
            className="api-error-banner-btn"
            onClick={handleRetry}
            disabled={retrying}
            data-testid="api-error-retry"
          >
            {retrying ? (
              <Loader2 size={14} className="api-error-spin" />
            ) : (
              <RefreshCw size={14} />
            )}
            <span>{retrying ? 'Retrying…' : 'Retry'}</span>
          </button>
        )}

        {showAction && (
          <button
            type="button"
            className="api-error-banner-btn"
            onClick={() => onAction(error.action)}
            data-testid="api-error-action"
          >
            {ActionIcon && <ActionIcon size={14} />}
            <span>{actionLabel}</span>
          </button>
        )}

        {onDismiss && (
          <button
            type="button"
            className="api-error-banner-dismiss"
            onClick={onDismiss}
            aria-label="Dismiss error"
            data-testid="api-error-dismiss"
          >
            <X size={14} />
          </button>
        )}
      </div>
    </div>
  )
}
