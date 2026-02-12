/**
 * Warning banner for unavailable backend capabilities.
 *
 * Extracted from App.jsx lines 1559-1564. Displays a warning when
 * essential panes are missing required capabilities.
 */

import React from 'react'

/**
 * @param {Object} props
 * @param {Array} props.unavailableEssentials - Essential panes missing capabilities
 */
export function CapabilityWarning({ unavailableEssentials }) {
  if (!unavailableEssentials || unavailableEssentials.length === 0) {
    return null
  }

  return (
    <div className="capability-warning">
      <strong>Warning:</strong> Some features are unavailable.
      Missing capabilities for: {unavailableEssentials.map((p) => p.title || p.id).join(', ')}.
    </div>
  )
}

export default CapabilityWarning
