/**
 * useDockLayout — DockView layout helper functions.
 *
 * Extracted from App.jsx. Provides:
 * - Sidebar group/panel discovery
 * - Center group/panel discovery
 * - Toggle sidebar/agent collapse
 * - Left sidebar group classification
 *
 * @param {Object} deps
 * @param {Object|null} deps.dockApi - DockView API instance
 * @param {string[]} deps.leftSidebarPanelIds - Panel IDs in left sidebar
 * @param {Object} deps.collapsed - Collapsed state { filetree, agent }
 * @param {Function} deps.setCollapsed - Collapsed state setter
 * @param {React.MutableRefObject} deps.panelSizesRef - Panel sizes ref
 * @param {React.MutableRefObject} deps.storagePrefixRef - Storage prefix ref
 * @param {React.MutableRefObject} deps.centerGroupRef - Center group ref
 * @param {number} deps.leftSidebarCollapsedWidth - Collapsed sidebar width
 * @param {React.MutableRefObject} deps.panelCollapsedRef - Panel collapsed sizes ref
 * @param {Function} deps.saveCollapsedState - Persist collapsed state
 * @param {Function} deps.savePanelSizes - Persist panel sizes
 */
import { useCallback } from 'react'

export default function useDockLayout({
  dockApi,
  leftSidebarPanelIds,
  collapsed,
  setCollapsed,
  panelSizesRef,
  storagePrefixRef,
  centerGroupRef,
  leftSidebarCollapsedWidth,
  panelCollapsedRef,
  saveCollapsedState,
  savePanelSizes,
}) {
  // --- Sidebar discovery ---

  const getLeftSidebarGroups = useCallback((api) => {
    if (!api) return []
    const groups = []
    const seen = new Set()
    leftSidebarPanelIds.forEach((panelId) => {
      const group = api.getPanel(panelId)?.group
      if (!group || seen.has(group.id)) return
      seen.add(group.id)
      groups.push(group)
    })
    return groups
  }, [leftSidebarPanelIds])

  const getLeftSidebarAnchorPanelId = useCallback((api) => {
    if (!api) return 'filetree'
    for (const panelId of leftSidebarPanelIds) {
      if (api.getPanel(panelId)) return panelId
    }
    return 'filetree'
  }, [leftSidebarPanelIds])

  const getLeftSidebarAnchorPosition = useCallback((api) => {
    if (!api) return undefined
    const anchorId = getLeftSidebarAnchorPanelId(api)
    return api.getPanel(anchorId)
      ? { direction: 'right', referencePanel: anchorId }
      : undefined
  }, [getLeftSidebarAnchorPanelId])

  // --- Group classification ---

  const isLeftSidebarGroup = useCallback((group) => {
    if (!group) return false
    const groupPanels = Array.isArray(group.panels) ? group.panels : []
    return groupPanels.some((panel) => {
      const panelId = typeof panel?.id === 'string' ? panel.id : ''
      return leftSidebarPanelIds.includes(panelId)
    })
  }, [leftSidebarPanelIds])

  // --- Center discovery ---

  const findCenterAnchorPanel = useCallback((api) => {
    if (!api) return null
    const allPanels = Array.isArray(api.panels) ? api.panels : []
    return allPanels.find((panel) => {
      if (!panel?.group || isLeftSidebarGroup(panel.group)) return false
      const panelId = typeof panel?.id === 'string' ? panel.id : ''
      return (
        panelId.startsWith('editor-')
        || panelId.startsWith('review-')
        || panelId.startsWith('deck-')
        || panelId.startsWith('chart-')
      )
    }) || null
  }, [isLeftSidebarGroup])

  const getLiveCenterGroup = useCallback((api) => {
    if (!api) return null
    const candidate = centerGroupRef.current
    if (!candidate) return null

    const groups = Array.isArray(api.groups) ? api.groups : []
    if (groups.includes(candidate) && !isLeftSidebarGroup(candidate)) {
      return candidate
    }
    if (candidate.id) {
      const matchingGroup = groups.find((group) => group?.id === candidate.id)
      if (matchingGroup && !isLeftSidebarGroup(matchingGroup)) {
        centerGroupRef.current = matchingGroup
        return matchingGroup
      }
    }
    centerGroupRef.current = null
    return null
  }, [isLeftSidebarGroup, centerGroupRef])

  // --- Toggle collapse ---

  const toggleFiletree = useCallback(() => {
    if (!collapsed.filetree && dockApi) {
      const leftGroups = getLeftSidebarGroups(dockApi)
      const currentWidth = leftGroups[0]?.api?.width
      const collapsedWidth = leftSidebarCollapsedWidth
      if (Number.isFinite(currentWidth) && currentWidth > collapsedWidth) {
        panelSizesRef.current = { ...panelSizesRef.current, filetree: currentWidth }
        savePanelSizes(panelSizesRef.current, storagePrefixRef.current)
      }
    }
    setCollapsed((prev) => {
      const next = { ...prev, filetree: !prev.filetree }
      saveCollapsedState(next, storagePrefixRef.current)
      return next
    })
  }, [collapsed.filetree, dockApi, getLeftSidebarGroups, leftSidebarCollapsedWidth, panelSizesRef, storagePrefixRef, setCollapsed, saveCollapsedState, savePanelSizes])

  const toggleAgent = useCallback(() => {
    if (!collapsed.agent && dockApi) {
      const agentPanel = dockApi.getPanel('agent')
      const agentGroup = agentPanel?.group
      if (agentGroup) {
        const currentWidth = agentGroup.api.width
        if (currentWidth > panelCollapsedRef.current.agent) {
          panelSizesRef.current = { ...panelSizesRef.current, agent: currentWidth }
          savePanelSizes(panelSizesRef.current, storagePrefixRef.current)
        }
      }
    }
    setCollapsed((prev) => {
      const next = { ...prev, agent: !prev.agent }
      saveCollapsedState(next, storagePrefixRef.current)
      return next
    })
  }, [collapsed.agent, dockApi, panelCollapsedRef, panelSizesRef, storagePrefixRef, setCollapsed, saveCollapsedState, savePanelSizes])

  return {
    getLeftSidebarGroups,
    getLeftSidebarAnchorPanelId,
    getLeftSidebarAnchorPosition,
    isLeftSidebarGroup,
    findCenterAnchorPanel,
    getLiveCenterGroup,
    toggleFiletree,
    toggleAgent,
  }
}
