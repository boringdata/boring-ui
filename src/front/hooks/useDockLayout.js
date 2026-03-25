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
import { useCallback, useEffect, useRef, useState } from 'react'

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
  sidebarToggleHostId,
  saveCollapsedState,
  savePanelSizes,
}) {
  const [activeSidebarPanelId, setActiveSidebarPanelId] = useState(
    () => leftSidebarPanelIds[0] || 'filetree',
  )
  const [filetreeActivityIntent, setFiletreeActivityIntent] = useState(null)
  const [catalogActivityIntent, setCatalogActivityIntent] = useState(null)
  const [sectionCollapsed, setSectionCollapsed] = useState({})
  const sectionSizesRef = useRef({})
  const SECTION_HEADER_HEIGHT = 30
  const LEFT_PANE_HEADER_HEIGHT = 42
  const PANEL_FOOTER_HEIGHT = 68
  const SIDEBAR_SECTION_BODY_MIN_HEIGHT = 40

  useEffect(() => {
    if (!leftSidebarPanelIds.includes(activeSidebarPanelId)) {
      setActiveSidebarPanelId(leftSidebarPanelIds[0] || 'filetree')
    }
  }, [activeSidebarPanelId, leftSidebarPanelIds])

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

  // --- Sidebar section helpers ---

  const getSidebarCollapsedHeight = useCallback((panelId) => {
    const isToggleHost = sidebarToggleHostId === panelId
    const hasFooter = panelId === 'filetree'
    return SECTION_HEADER_HEIGHT
      + (isToggleHost ? LEFT_PANE_HEADER_HEIGHT : 0)
      + (hasFooter ? PANEL_FOOTER_HEIGHT : 0)
  }, [sidebarToggleHostId])

  const getSidebarExpandedMinHeight = useCallback(
    (panelId) => getSidebarCollapsedHeight(panelId) + SIDEBAR_SECTION_BODY_MIN_HEIGHT,
    [getSidebarCollapsedHeight],
  )

  const toggleSectionCollapse = useCallback((panelId) => {
    if (!dockApi) return
    const panel = dockApi.getPanel(panelId)
    const group = panel?.group
    const collapsedHeight = getSidebarCollapsedHeight(panelId)
    const expandedMinHeight = getSidebarExpandedMinHeight(panelId)
    const currentlyCollapsed = !!sectionCollapsed[panelId]
    if (group && !currentlyCollapsed) {
      const currentHeight = group.api.height
      if (currentHeight > collapsedHeight) {
        sectionSizesRef.current = { ...sectionSizesRef.current, [panelId]: currentHeight }
      }
    }
    const isOnlyPanel = leftSidebarPanelIds.length <= 1
    setSectionCollapsed((prev) => {
      const next = { ...prev, [panelId]: !prev[panelId] }
      if (group) {
        if (next[panelId]) {
          const allWillBeCollapsed = !isOnlyPanel && leftSidebarPanelIds.every((id) => next[id])
          const hasFooter = panelId === 'filetree'
          const keepFlexible = isOnlyPanel || (allWillBeCollapsed && hasFooter)
          group.api.setConstraints({
            minimumHeight: collapsedHeight,
            maximumHeight: keepFlexible ? Number.MAX_SAFE_INTEGER : collapsedHeight,
          })
          if (!keepFlexible) {
            group.api.setSize({ height: collapsedHeight })
          }
          if (allWillBeCollapsed && !hasFooter) {
            const filetreeGroup = dockApi.getPanel('filetree')?.group
            if (filetreeGroup) {
              const filetreeCollapsedHeight = getSidebarCollapsedHeight('filetree')
              filetreeGroup.api.setConstraints({
                minimumHeight: filetreeCollapsedHeight,
                maximumHeight: Number.MAX_SAFE_INTEGER,
              })
            }
          }
        } else {
          if (!isOnlyPanel) {
            leftSidebarPanelIds.forEach((siblingId) => {
              if (siblingId === panelId) return
              const siblingGroup = dockApi.getPanel(siblingId)?.group
              if (siblingGroup) {
                const siblingIsCollapsed = !!next[siblingId]
                const siblingCollapsedHeight = getSidebarCollapsedHeight(siblingId)
                siblingGroup.api.setConstraints({
                  minimumHeight: siblingIsCollapsed
                    ? siblingCollapsedHeight
                    : getSidebarExpandedMinHeight(siblingId),
                  maximumHeight: siblingIsCollapsed
                    ? siblingCollapsedHeight
                    : Number.MAX_SAFE_INTEGER,
                })
                if (siblingIsCollapsed) {
                  siblingGroup.api.setSize({ height: siblingCollapsedHeight })
                }
              }
            })
          }
          group.api.setConstraints({
            minimumHeight: expandedMinHeight,
            maximumHeight: Number.MAX_SAFE_INTEGER,
          })
          const savedHeight = sectionSizesRef.current[panelId]
          if (Number.isFinite(savedHeight) && savedHeight > expandedMinHeight) {
            group.api.setSize({ height: savedHeight })
          } else {
            group.api.setSize({ height: expandedMinHeight })
          }
        }
      }
      return next
    })
  }, [
    dockApi,
    getSidebarCollapsedHeight,
    getSidebarExpandedMinHeight,
    leftSidebarPanelIds,
    sectionCollapsed,
  ])

  const activateSidebarPanel = useCallback((panelId, options = {}) => {
    if (!panelId || !dockApi) return
    if (panelId === 'filetree' && options?.mode) {
      setFiletreeActivityIntent({
        panelId: 'filetree',
        mode: options.mode,
        token: Date.now(),
      })
    }
    if (panelId === 'data-catalog' && options?.mode) {
      setCatalogActivityIntent({
        panelId: 'data-catalog',
        mode: options.mode,
        token: Date.now(),
      })
    }

    const activate = () => {
      const panel = dockApi.getPanel(panelId)
      if (!panel) return
      if (sectionCollapsed[panelId]) {
        toggleSectionCollapse(panelId)
      }
      panel.api.setActive()
      setActiveSidebarPanelId(panelId)
    }

    if (collapsed.filetree) {
      toggleFiletree()
      const scheduleActivate = (
        typeof window !== 'undefined' && typeof window.requestAnimationFrame === 'function'
      )
        ? window.requestAnimationFrame.bind(window)
        : (callback) => globalThis.setTimeout(callback, 0)
      scheduleActivate(activate)
      return
    }
    activate()
  }, [
    collapsed.filetree,
    dockApi,
    sectionCollapsed,
    toggleFiletree,
    toggleSectionCollapse,
  ])

  return {
    getLeftSidebarGroups,
    getLeftSidebarAnchorPanelId,
    getLeftSidebarAnchorPosition,
    isLeftSidebarGroup,
    findCenterAnchorPanel,
    getLiveCenterGroup,
    toggleFiletree,
    toggleAgent,
    activeSidebarPanelId,
    setActiveSidebarPanelId,
    filetreeActivityIntent,
    catalogActivityIntent,
    sectionCollapsed,
    getSidebarCollapsedHeight,
    getSidebarExpandedMinHeight,
    toggleSectionCollapse,
    activateSidebarPanel,
  }
}
