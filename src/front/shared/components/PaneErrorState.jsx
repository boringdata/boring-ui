/**
 * PaneErrorState - Error display component for panes with missing capabilities.
 *
 * Shows a clear, actionable error state when a pane cannot render
 * due to missing backend capabilities or features.
 *
 * @module components/PaneErrorState
 */

import { AlertCircle, RotateCcw } from 'lucide-react'

/**
 * Error state component for panes with missing capabilities.
 *
 * @param {Object} props
 * @param {string} props.paneId - ID of the affected pane
 * @param {string} props.paneTitle - Title of the affected pane
 * @param {string[]} [props.missingFeatures] - Missing feature names
 * @param {string[]} [props.missingRouters] - Missing router names
 * @param {Function} [props.onRetry] - Retry callback (e.g., refetch capabilities)
 */
export default function PaneErrorState({
  paneId,
  paneTitle,
  missingFeatures = [],
  missingRouters = [],
  onRetry,
}) {
  const allMissing = [...missingFeatures, ...missingRouters]

  return (
    <div className="pane-error-state" role="alert">
      <AlertCircle className="pane-error-icon" size={40} />
      <h3 className="pane-error-title">
        {paneTitle || paneId} Unavailable
      </h3>
      <p className="pane-error-message">
        This feature requires a service that isn't responding right now.
      </p>
      {allMissing.length > 0 && (
        <ul className="pane-error-list">
          {allMissing.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="pane-error-retry"
        >
          <RotateCcw size={14} />
          Retry
        </button>
      )}
      <p className="pane-error-hint">
        Try refreshing, or check that the backend is running.
      </p>
    </div>
  )
}
