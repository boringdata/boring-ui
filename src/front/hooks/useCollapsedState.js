/**
 * Applies collapsed/expanded state to Dockview groups as a side effect.
 *
 * Extracted from App.jsx lines 243-324. Handles:
 * - First-run detection (skip setSize on initial mount to avoid
 *   conflicting with layout restoration)
 * - Constraint and size application per panel
 * - Width dimension for filetree/terminal, height for shell
 */

import { useEffect, useRef } from 'react'

/**
 * Panel collapse/expand configuration.
 * @typedef {Object} CollapsePanelConfig
 * @property {string} panelId - Dockview panel ID (e.g., 'filetree')
 * @property {'width'|'height'} dimension - Which dimension to constrain
 */

/**
 * Default panel collapse configurations matching App.jsx.
 */
export const DEFAULT_COLLAPSE_PANELS = [
  { panelId: 'filetree', dimension: 'width' },
  { panelId: 'terminal', dimension: 'width' },
  { panelId: 'shell', dimension: 'height' },
]

/**
 * Applies collapsed/expanded constraints and sizes to a single panel group.
 *
 * @param {Object} group - Dockview group from panel.group
 * @param {boolean} isCollapsed - Whether the panel is collapsed
 * @param {number} collapsedSize - Size when collapsed (min=max=this)
 * @param {number} minSize - Minimum size when expanded
 * @param {number} savedSize - Saved size to restore when expanding
 * @param {'width'|'height'} dimension - Dimension to control
 * @param {boolean} isFirstRun - Skip setSize for expanded on first run
 */
function applyPanelState(
  group,
  isCollapsed,
  collapsedSize,
  minSize,
  savedSize,
  dimension,
  isFirstRun,
) {
  if (!group) return

  const minKey = dimension === 'width' ? 'minimumWidth' : 'minimumHeight'
  const maxKey = dimension === 'width' ? 'maximumWidth' : 'maximumHeight'

  if (isCollapsed) {
    group.api.setConstraints({ [minKey]: collapsedSize, [maxKey]: collapsedSize })
    group.api.setSize({ [dimension]: collapsedSize })
  } else {
    group.api.setConstraints({ [minKey]: minSize, [maxKey]: Infinity })
    if (!isFirstRun) {
      const effectiveSize =
        dimension === 'height' ? Math.max(savedSize, minSize) : savedSize
      group.api.setSize({ [dimension]: effectiveSize })
    }
  }
}

/**
 * Effect hook that synchronizes collapsed state to Dockview groups.
 *
 * On first run, only constraints are applied (no setSize for expanded panels)
 * to avoid conflicting with layout restoration. Subsequent runs apply both
 * constraints and sizes.
 *
 * @param {Object} options
 * @param {Object|null} options.dockApi - Dockview API instance
 * @param {Object} options.collapsed - { filetree, terminal, shell } booleans
 * @param {Object} options.panelSizesRef - Ref to saved panel sizes
 * @param {Object} options.panelCollapsedRef - Ref to collapsed size thresholds
 * @param {Object} options.panelMinRef - Ref to minimum panel sizes
 * @param {Object} options.collapsedEffectRan - Ref for first-run detection
 * @param {Array} [options.panels] - Panel configs (defaults to DEFAULT_COLLAPSE_PANELS)
 */
export function useCollapsedEffect({
  dockApi,
  collapsed,
  panelSizesRef,
  panelCollapsedRef,
  panelMinRef,
  collapsedEffectRan,
  panels = DEFAULT_COLLAPSE_PANELS,
}) {
  useEffect(() => {
    if (!dockApi) return

    const isFirstRun = !collapsedEffectRan.current
    if (isFirstRun) {
      collapsedEffectRan.current = true
    }

    for (const { panelId, dimension } of panels) {
      const panel = dockApi.getPanel(panelId)
      const group = panel?.group

      applyPanelState(
        group,
        collapsed[panelId],
        panelCollapsedRef?.current?.[panelId] ?? 0,
        panelMinRef?.current?.[panelId] ?? 0,
        panelSizesRef?.current?.[panelId] ?? 0,
        dimension,
        isFirstRun,
      )
    }
  }, [dockApi, collapsed])
}
