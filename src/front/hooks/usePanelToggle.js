/**
 * Hook for generating panel toggle callbacks.
 *
 * Reduces the repeated toggle pattern in App.jsx (lines 131-189) into a
 * declarative configuration. Each toggle captures the current panel size
 * before collapsing and persists both collapsed state and panel sizes.
 */

import { useMemo } from 'react'
import { createPanelToggle } from '../utils/panelToggleUtils'
import { savePanelSizes, saveCollapsedState } from '../layout'

/**
 * Default panel toggle configurations matching App.jsx structure.
 *
 * - filetree/terminal are width-based (vertical panels)
 * - shell is height-based (horizontal panel)
 */
export const DEFAULT_TOGGLE_CONFIGS = [
  { panelId: 'filetree', stateKey: 'filetree', dimension: 'width' },
  { panelId: 'terminal', stateKey: 'terminal', dimension: 'width' },
  { panelId: 'shell', stateKey: 'shell', dimension: 'height' },
]

/**
 * Creates toggle functions for collapsible panels.
 *
 * Each toggle:
 * 1. Captures the current panel size before collapsing (if above threshold)
 * 2. Persists the size to localStorage
 * 3. Flips the collapsed state and persists it
 *
 * @param {Object} options
 * @param {Object|null} options.dockApi - Dockview API instance
 * @param {Object} options.collapsed - Current collapsed state { filetree, terminal, shell }
 * @param {Function} options.setCollapsed - State setter for collapsed
 * @param {Object} options.panelSizesRef - Ref to panel sizes object
 * @param {Object} options.panelCollapsedRef - Ref to collapsed size thresholds
 * @param {Object} options.storagePrefixRef - Ref to storage prefix string
 * @param {Array} [options.panels] - Panel configs (defaults to DEFAULT_TOGGLE_CONFIGS)
 * @returns {Object} Toggle functions keyed by stateKey (e.g., { filetree, terminal, shell })
 */
export function usePanelToggle({
  dockApi,
  collapsed,
  setCollapsed,
  panelSizesRef,
  panelCollapsedRef,
  storagePrefixRef,
  panels = DEFAULT_TOGGLE_CONFIGS,
}) {
  return useMemo(() => {
    const toggles = {}

    for (const { panelId, stateKey, dimension } of panels) {
      toggles[stateKey] = () => {
        // Capture size before collapsing
        if (!collapsed[stateKey] && dockApi) {
          const panel = dockApi.getPanel(panelId)
          const group = panel?.group
          if (group) {
            const currentSize = group.api[dimension]
            const threshold = panelCollapsedRef?.current?.[stateKey] ?? 0
            if (
              typeof currentSize === 'number' &&
              currentSize > threshold &&
              panelSizesRef?.current
            ) {
              panelSizesRef.current = {
                ...panelSizesRef.current,
                [stateKey]: currentSize,
              }
              savePanelSizes(panelSizesRef.current, storagePrefixRef?.current)
            }
          }
        }

        // Toggle collapsed state and persist
        setCollapsed((prev) => {
          const next = { ...prev, [stateKey]: !prev[stateKey] }
          saveCollapsedState(next, storagePrefixRef?.current)
          return next
        })
      }
    }

    return toggles
  }, [
    dockApi,
    collapsed,
    setCollapsed,
    panelSizesRef,
    panelCollapsedRef,
    storagePrefixRef,
    panels,
  ])
}
