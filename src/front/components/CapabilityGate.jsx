/**
 * CapabilityGate - HOC wrapper for capability-gated pane rendering.
 *
 * This component wraps panes and checks if required capabilities are available.
 * If not, it renders a PaneErrorState instead of the actual pane.
 *
 * @module components/CapabilityGate
 */

import { useContext, createContext } from 'react'
import PaneErrorState from './PaneErrorState'
import { getPane, checkRequirements } from '../registry/panes'

/**
 * Context for passing capabilities to pane wrappers.
 */
export const CapabilitiesContext = createContext(null)

/**
 * Hook to access capabilities from context.
 * @returns {Object|null} Capabilities object or null
 */
export const useCapabilitiesContext = () => useContext(CapabilitiesContext)

/**
 * Create a capability-gated version of a pane component.
 *
 * @param {string} paneId - ID of the pane in the registry
 * @param {React.ComponentType} Component - The pane component to wrap
 * @returns {React.ComponentType} Wrapped component with capability checking
 */
export function createCapabilityGatedPane(paneId, Component) {
  function CapabilityGatedPane(props) {
    const capabilities = useCapabilitiesContext()
    const paneConfig = getPane(paneId)

    // If no capabilities context, render component (backwards compatibility)
    if (!capabilities) {
      return <Component {...props} />
    }

    // Check if requirements are met
    if (checkRequirements(paneId, capabilities)) {
      return <Component {...props} />
    }

    // Requirements not met - show error state
    const missingRequiredFeatures = (paneConfig?.requiresFeatures || []).filter(
      (f) => !capabilities?.features?.[f]
    )
    const requiresAny = paneConfig?.requiresAnyFeatures || []
    const anySatisfied = requiresAny.some((f) => capabilities?.features?.[f])
    const missingAnyFeatures = anySatisfied ? [] : requiresAny
    const missingFeatures = [...missingRequiredFeatures, ...missingAnyFeatures]
    const missingRouters = (paneConfig?.requiresRouters || []).filter(
      (r) => !capabilities?.features?.[r]
    )

    return (
      <PaneErrorState
        paneId={paneId}
        paneTitle={paneConfig?.title}
        missingFeatures={missingFeatures}
        missingRouters={missingRouters}
      />
    )
  }

  CapabilityGatedPane.displayName = `CapabilityGated(${Component.displayName || Component.name || paneId})`

  return CapabilityGatedPane
}

// Default export is the createCapabilityGatedPane function
export default createCapabilityGatedPane
