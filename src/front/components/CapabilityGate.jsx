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
import PaneLoadingState from './PaneLoadingState'
import { getPane, checkRequirements } from '../registry/panes'

/**
 * Context for passing capabilities to pane wrappers.
 */
export const CapabilitiesContext = createContext(null)
export const CapabilitiesStatusContext = createContext(null)

/**
 * Hook to access capabilities from context.
 * @returns {Object|null} Capabilities object or null
 */
export const useCapabilitiesContext = () => useContext(CapabilitiesContext)
export const useCapabilitiesStatusContext = () => useContext(CapabilitiesStatusContext)

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
    const capabilitiesStatus = useCapabilitiesStatusContext()
    const paneConfig = getPane(paneId)
    const capabilitiesPending = capabilitiesStatus?.pending === true
    const abstractCapabilities = capabilities?.capabilities || {}

    // During capability bootstrap/retry, render a loading state instead of
    // a transient "missing capability" error.
    if (capabilitiesPending) {
      return <PaneLoadingState paneId={paneId} paneTitle={paneConfig?.title} />
    }

    // If no capabilities context, render component (backwards compatibility)
    if (!capabilities) {
      return <Component {...props} />
    }

    // Check if requirements are met
    if (checkRequirements(paneId, capabilities)) {
      return <Component {...props} />
    }

    // Requirements not met - show error state
    const missingRequiredCapabilities = (paneConfig?.requiresCapabilities || []).filter(
      (capability) => !abstractCapabilities?.[capability]
    )
    const missingRequiredFeatures = (paneConfig?.requiresFeatures || []).filter(
      (f) => !capabilities?.features?.[f]
    )
    const requiresAny = paneConfig?.requiresAnyFeatures || []
    const anySatisfied = requiresAny.some((f) => capabilities?.features?.[f])
    const missingAnyFeatures = anySatisfied ? [] : requiresAny
    const missingFeatures = [...missingRequiredCapabilities, ...missingRequiredFeatures, ...missingAnyFeatures]
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
