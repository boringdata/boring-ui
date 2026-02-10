/**
 * Panel collapse/expand toggle hook.
 *
 * Generates memoized toggle callbacks for each collapsible panel,
 * replacing three near-identical useCallback blocks in App.jsx.
 *
 * @module hooks/usePanelToggle
 */

import { useCallback } from 'react'
import { createPanelToggle } from '../utils/panelToggleUtils'

/**
 * Panel toggle definitions.
 * Each entry maps a panel key to its Dockview panel ID and resize dimension.
 */
const PANEL_TOGGLES = [
  { key: 'filetree', panelId: 'filetree', dimension: 'width' },
  { key: 'terminal', panelId: 'terminal', dimension: 'width' },
  { key: 'shell', panelId: 'shell', dimension: 'height' },
]

/**
 * Create toggle functions for all collapsible panels.
 *
 * @param {Object} options
 * @param {Object|null} options.dockApi - Dockview API
 * @param {Object} options.collapsed - { filetree, terminal, shell } booleans
 * @param {Function} options.setCollapsed - State setter
 * @param {Object} options.panelSizesRef - Ref to saved panel sizes
 * @param {Object} options.panelCollapsedRef - Ref to collapsed threshold sizes
 * @param {Object} options.storagePrefixRef - Ref to storage prefix string
 * @returns {{ toggleFiletree: Function, toggleTerminal: Function, toggleShell: Function }}
 */
export function usePanelToggle({
  dockApi,
  collapsed,
  setCollapsed,
  panelSizesRef,
  panelCollapsedRef,
  storagePrefixRef,
}) {
  const toggleFiletree = useCallback(
    () => createPanelToggle({
      panelId: 'filetree', panelKey: 'filetree', dimension: 'width',
      dockApi, isCollapsed: collapsed.filetree, setCollapsed,
      panelSizesRef, collapsedThreshold: panelCollapsedRef.current.filetree,
      storagePrefix: storagePrefixRef.current,
    })(),
    [collapsed.filetree, dockApi, setCollapsed, panelSizesRef, panelCollapsedRef, storagePrefixRef],
  )

  const toggleTerminal = useCallback(
    () => createPanelToggle({
      panelId: 'terminal', panelKey: 'terminal', dimension: 'width',
      dockApi, isCollapsed: collapsed.terminal, setCollapsed,
      panelSizesRef, collapsedThreshold: panelCollapsedRef.current.terminal,
      storagePrefix: storagePrefixRef.current,
    })(),
    [collapsed.terminal, dockApi, setCollapsed, panelSizesRef, panelCollapsedRef, storagePrefixRef],
  )

  const toggleShell = useCallback(
    () => createPanelToggle({
      panelId: 'shell', panelKey: 'shell', dimension: 'height',
      dockApi, isCollapsed: collapsed.shell, setCollapsed,
      panelSizesRef, collapsedThreshold: panelCollapsedRef.current.shell,
      storagePrefix: storagePrefixRef.current,
    })(),
    [collapsed.shell, dockApi, setCollapsed, panelSizesRef, panelCollapsedRef, storagePrefixRef],
  )

  return { toggleFiletree, toggleTerminal, toggleShell }
}
