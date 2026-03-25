/**
 * Frontend state snapshot utilities.
 *
 * Captures DockView panel state for backend persistence (ui_state router).
 * Extracted from App.jsx for testability.
 *
 * @module utils/frontendState
 */

const MAX_SNAPSHOT_DEPTH = 4
const MAX_SNAPSHOT_ARRAY_ITEMS = 32
const MAX_SNAPSHOT_OBJECT_KEYS = 64
const MAX_SNAPSHOT_STRING_LENGTH = 2048

export const sanitizeSnapshotValue = (value, depth = 0, seen = new WeakSet()) => {
  if (value == null) return value
  const kind = typeof value
  if (kind === 'string') {
    if (value.length <= MAX_SNAPSHOT_STRING_LENGTH) {
      return value
    }
    return `${value.slice(0, MAX_SNAPSHOT_STRING_LENGTH)}...`
  }
  if (kind === 'number' || kind === 'boolean') {
    return value
  }
  if (kind === 'bigint') {
    return value.toString()
  }
  if (kind === 'function' || kind === 'symbol' || kind === 'undefined') {
    return undefined
  }
  if (depth >= MAX_SNAPSHOT_DEPTH) return undefined

  if (Array.isArray(value)) {
    return value
      .slice(0, MAX_SNAPSHOT_ARRAY_ITEMS)
      .map((item) => sanitizeSnapshotValue(item, depth + 1, seen))
      .filter((item) => item !== undefined)
  }

  if (kind === 'object') {
    if (seen.has(value)) return undefined
    seen.add(value)
    const out = {}
    Object.entries(value)
      .slice(0, MAX_SNAPSHOT_OBJECT_KEYS)
      .forEach(([key, entry]) => {
        const sanitized = sanitizeSnapshotValue(entry, depth + 1, seen)
        if (sanitized !== undefined) out[key] = sanitized
      })
    return out
  }

  return undefined
}

export const collectFrontendStateSnapshot = (api, clientId, projectRoot) => {
  const activePanelId = api?.activePanel?.id ?? null
  const panels = Array.isArray(api?.panels)
    ? api.panels
    : typeof api?.getPanels === 'function'
      ? api.getPanels()
      : []

  const openPanels = panels
    .filter((panel) => typeof panel?.id === 'string' && panel.id.length > 0)
    .map((panel) => {
      const params = sanitizeSnapshotValue(
        panel?.params ?? panel?.api?.params ?? panel?.api?.parameters ?? {},
      ) || {}
      const entry = {
        id: panel.id,
        component: panel?.api?.component ?? panel?.component ?? null,
        title: panel?.api?.title ?? panel?.title ?? null,
        active: panel.id === activePanelId,
        params,
      }
      if (panel?.group?.id) entry.group_id = panel.group.id
      return entry
    })

  return {
    client_id: clientId,
    project_root: projectRoot || null,
    active_panel_id: activePanelId,
    open_panels: openPanels,
    captured_at_ms: Date.now(),
    meta: {
      pane_count: openPanels.length,
    },
  }
}

export const createFrontendStateClientId = () => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `client-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

export const getFrontendStateClientId = (storagePrefix) => {
  const key = `${storagePrefix}-frontend-state-client-id`
  try {
    const existing = window.sessionStorage?.getItem(key)
    if (existing) return existing
    const created = createFrontendStateClientId()
    window.sessionStorage?.setItem(key, created)
    return created
  } catch {
    return createFrontendStateClientId()
  }
}
