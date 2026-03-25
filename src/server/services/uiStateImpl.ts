/**
 * UI State service — in-memory storage for workspace panel layout/state.
 * Mirrors Python's modules/ui_state/router.py.
 *
 * In-memory only (same as Python). Data lost on restart.
 * Future: DB-backed for durability.
 */

export interface UiStateSnapshot {
  client_id: string
  panes: Record<string, unknown>[]
  active_panel?: string
  metadata?: Record<string, unknown>
  saved_at: string
}

export interface UiCommand {
  id: string
  type: string // 'focus_panel' | 'open_panel' | 'close_panel'
  payload: Record<string, unknown>
  created_at: string
  consumed: boolean
}

// In-memory state store (per-workspace)
const stateStore = new Map<string, Map<string, UiStateSnapshot>>()
const commandQueue = new Map<string, UiCommand[]>()

function getWorkspaceStore(workspaceKey: string): Map<string, UiStateSnapshot> {
  let store = stateStore.get(workspaceKey)
  if (!store) {
    store = new Map()
    stateStore.set(workspaceKey, store)
  }
  return store
}

export function saveState(workspaceKey: string, snapshot: UiStateSnapshot): void {
  const store = getWorkspaceStore(workspaceKey)
  store.set(snapshot.client_id, { ...snapshot, saved_at: new Date().toISOString() })
}

export function getState(workspaceKey: string, clientId: string): UiStateSnapshot | null {
  return getWorkspaceStore(workspaceKey).get(clientId) ?? null
}

export function getLatestState(workspaceKey: string): UiStateSnapshot | null {
  const store = getWorkspaceStore(workspaceKey)
  let latest: UiStateSnapshot | null = null
  for (const snap of store.values()) {
    if (!latest || snap.saved_at > latest.saved_at) latest = snap
  }
  return latest
}

export function listStates(workspaceKey: string): UiStateSnapshot[] {
  return Array.from(getWorkspaceStore(workspaceKey).values())
}

export function deleteState(workspaceKey: string, clientId: string): boolean {
  return getWorkspaceStore(workspaceKey).delete(clientId)
}

export function clearStates(workspaceKey: string): void {
  stateStore.delete(workspaceKey)
}

export function enqueueCommand(workspaceKey: string, command: Omit<UiCommand, 'id' | 'created_at' | 'consumed'>): UiCommand {
  const cmd: UiCommand = {
    id: crypto.randomUUID(),
    ...command,
    created_at: new Date().toISOString(),
    consumed: false,
  }
  const queue = commandQueue.get(workspaceKey) ?? []
  queue.push(cmd)
  commandQueue.set(workspaceKey, queue)
  return cmd
}

export function pollNextCommand(workspaceKey: string, clientId: string): UiCommand | null {
  const queue = commandQueue.get(workspaceKey) ?? []
  const idx = queue.findIndex((c) => !c.consumed)
  if (idx === -1) return null
  queue[idx].consumed = true
  return queue[idx]
}

export function getPanes(workspaceKey: string, clientId?: string): Record<string, unknown>[] {
  if (clientId) {
    const snap = getState(workspaceKey, clientId)
    return snap?.panes ?? []
  }
  const latest = getLatestState(workspaceKey)
  return latest?.panes ?? []
}
