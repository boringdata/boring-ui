/**
 * DockView panel helper utilities.
 *
 * Pure functions for querying and classifying DockView panels.
 * Extracted from App.jsx for testability and clarity.
 *
 * @module utils/dockHelpers
 */

export const isCenterContentPanel = (panel, registry) => {
  if (!panel?.id || panel.id === 'empty-center') return false
  if (panel.id.startsWith('editor-') || panel.id.startsWith('review-')) return true

  const componentId = panel?.api?.component ?? panel?.component
  if (typeof componentId !== 'string' || componentId.length === 0) return false
  const paneConfig = registry?.get?.(componentId)
  return paneConfig?.placement === 'center'
}

export const listDockPanels = (api) => {
  if (!api) return []
  if (Array.isArray(api.panels)) return api.panels
  if (typeof api.getPanels === 'function') return api.getPanels()
  return []
}

export const listDockGroups = (api) => {
  if (!api) return []
  if (Array.isArray(api.groups)) return api.groups
  if (typeof api.getGroups === 'function') return api.getGroups()
  return []
}

export const getPanelComponent = (panel) =>
  panel?.api?.component ?? panel?.component ?? ''

export const countAgentPanels = (api, family) => {
  const panels = listDockPanels(api)
  if (family === 'terminal') {
    return panels.filter((panel) => getPanelComponent(panel) === 'terminal').length
  }
  if (family === 'agent') {
    return panels.filter((panel) => getPanelComponent(panel) === 'agent').length
  }
  return 0
}

export const panelIdToAgentFamily = (panelId) => {
  if (panelId === 'terminal' || panelId.startsWith('terminal-chat-')) return 'terminal'
  if (panelId === 'agent' || panelId.startsWith('agent-chat-')) return 'agent'
  return null
}

export const countAllAgentPanels = (api) =>
  countAgentPanels(api, 'terminal')
  + countAgentPanels(api, 'agent')
