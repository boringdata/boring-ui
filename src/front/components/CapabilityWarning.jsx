/**
 * Warning banner displayed when essential backend capabilities are unavailable.
 *
 * @param {Object} props
 * @param {Array} props.unavailableEssentials - Panes missing required capabilities
 */
export default function CapabilityWarning({ unavailableEssentials }) {
  if (!unavailableEssentials || unavailableEssentials.length === 0) return null

  return (
    <div className="capability-warning">
      <strong>Warning:</strong> Some features are unavailable.
      Missing capabilities for: {unavailableEssentials.map(p => p.title || p.id).join(', ')}.
    </div>
  )
}
