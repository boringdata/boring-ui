/**
 * Collapsed panel state effect.
 *
 * Applies collapsed/expanded sizes to Dockview groups whenever the
 * collapsed state changes, with first-run detection to avoid
 * overriding sizes from layout restoration.
 *
 * @module hooks/useCollapsedState
 */

import { useEffect } from 'react'
import { applyPanelSizes } from '../utils/layoutUtils'

/**
 * Sync collapsed state changes to the Dockview layout.
 *
 * On first invocation (first-run), only constraints and collapsed sizes
 * are applied — expanded sizes are skipped because layout restoration
 * already set them. On subsequent calls, full size application occurs.
 *
 * @param {Object} options
 * @param {Object|null} options.dockApi - Dockview API
 * @param {Object} options.collapsed - { filetree, terminal, shell } booleans
 * @param {Object} options.panelSizesRef - Ref to saved panel sizes
 * @param {Object} options.panelMinRef - Ref to panel minimums
 * @param {Object} options.panelCollapsedRef - Ref to collapsed thresholds
 * @param {Object} options.collapsedEffectRan - Ref tracking first-run
 */
export function useCollapsedState({
  dockApi,
  collapsed,
  panelSizesRef,
  panelMinRef,
  panelCollapsedRef,
  collapsedEffectRan,
}) {
  useEffect(() => {
    if (!dockApi) return

    const isFirstRun = !collapsedEffectRan.current
    if (isFirstRun) {
      collapsedEffectRan.current = true
    }

    applyPanelSizes(dockApi, {
      collapsed,
      panelSizes: panelSizesRef.current,
      panelMin: panelMinRef.current,
      panelCollapsed: panelCollapsedRef.current,
      setExpandedSizes: !isFirstRun,
    })
  }, [dockApi, collapsed, panelSizesRef, panelMinRef, panelCollapsedRef, collapsedEffectRan])
}
