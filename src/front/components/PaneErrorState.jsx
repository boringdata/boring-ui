/**
 * PaneErrorState - Error display component for panes with missing capabilities.
 *
 * This component shows a clear error state when a pane cannot render
 * due to missing backend capabilities or features.
 *
 * @module components/PaneErrorState
 */

import { AlertCircle } from 'lucide-react'

/**
 * Error state component for panes with missing capabilities.
 *
 * @param {Object} props
 * @param {string} props.paneId - ID of the affected pane
 * @param {string} props.paneTitle - Title of the affected pane
 * @param {string[]} [props.missingFeatures] - Missing feature names
 * @param {string[]} [props.missingRouters] - Missing router names
 */
export default function PaneErrorState({
  paneId,
  paneTitle,
  missingFeatures = [],
  missingRouters = [],
}) {
  const allMissing = [...missingFeatures, ...missingRouters]

  return (
    <div className="pane-error-state">
      <AlertCircle className="pane-error-icon" size={48} />
      <h3 className="pane-error-title">
        {paneTitle || paneId} Unavailable
      </h3>
      <p className="pane-error-message">
        This panel requires backend capabilities that are not available.
      </p>
      {allMissing.length > 0 && (
        <ul className="pane-error-list">
          {allMissing.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
      <p className="pane-error-hint">
        Check that the API server is running with the required features enabled.
      </p>
    </div>
  )
}
