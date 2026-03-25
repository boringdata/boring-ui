/**
 * UI State HTTP routes at /api/v1/ui/*.
 * In-memory state persistence for workspace panel layout.
 */
import type { FastifyInstance } from 'fastify'
import {
  saveState,
  getState,
  getLatestState,
  listStates,
  deleteState,
  clearStates,
  enqueueCommand,
  pollNextCommand,
  getPanes,
  type UiStateSnapshot,
} from '../services/uiStateImpl.js'

export async function registerUiStateRoutes(app: FastifyInstance): Promise<void> {
  // Use workspace root as default workspace key
  const getKey = () => app.config.workspaceRoot

  // PUT /ui/state — save UI snapshot
  app.put('/ui/state', async (request) => {
    const body = request.body as Partial<UiStateSnapshot>
    const snapshot: UiStateSnapshot = {
      client_id: body.client_id || 'default',
      panes: body.panes || [],
      active_panel: body.active_panel,
      metadata: body.metadata,
      saved_at: new Date().toISOString(),
    }
    saveState(getKey(), snapshot)
    return { ok: true, saved: true }
  })

  // POST /ui/state — alias for PUT
  app.post('/ui/state', async (request) => {
    const body = request.body as Partial<UiStateSnapshot>
    const snapshot: UiStateSnapshot = {
      client_id: body.client_id || 'default',
      panes: body.panes || [],
      active_panel: body.active_panel,
      metadata: body.metadata,
      saved_at: new Date().toISOString(),
    }
    saveState(getKey(), snapshot)
    return { ok: true, saved: true }
  })

  // GET /ui/state — list all states
  app.get('/ui/state', async () => {
    return { ok: true, states: listStates(getKey()) }
  })

  // GET /ui/state/latest — most recent
  app.get('/ui/state/latest', async () => {
    const state = getLatestState(getKey())
    return { ok: true, state }
  })

  // GET /ui/state/:clientId — specific client
  app.get<{ Params: { clientId: string } }>('/ui/state/:clientId', async (request) => {
    const state = getState(getKey(), request.params.clientId)
    return { ok: true, state }
  })

  // DELETE /ui/state/:clientId — delete specific
  app.delete<{ Params: { clientId: string } }>('/ui/state/:clientId', async (request) => {
    const deleted = deleteState(getKey(), request.params.clientId)
    return { ok: true, deleted }
  })

  // DELETE /ui/state — clear all
  app.delete('/ui/state', async () => {
    clearStates(getKey())
    return { ok: true, cleared: true }
  })

  // GET /ui/panes — panel list
  app.get('/ui/panes', async (request) => {
    const { client_id } = request.query as { client_id?: string }
    return { ok: true, panes: getPanes(getKey(), client_id) }
  })

  // GET /ui/panes/:clientId — panel list for client
  app.get<{ Params: { clientId: string } }>('/ui/panes/:clientId', async (request) => {
    return { ok: true, panes: getPanes(getKey(), request.params.clientId) }
  })

  // POST /ui/commands — enqueue UI command
  app.post('/ui/commands', async (request) => {
    const body = request.body as { type: string; payload?: Record<string, unknown> }
    const cmd = enqueueCommand(getKey(), {
      type: body.type,
      payload: body.payload || {},
    })
    return { ok: true, command: cmd }
  })

  // GET /ui/commands/next — poll for next command
  app.get('/ui/commands/next', async (request) => {
    const { client_id } = request.query as { client_id?: string }
    const cmd = pollNextCommand(getKey(), client_id || 'default')
    return { ok: true, command: cmd }
  })

  // POST /ui/focus — shortcut for focus command
  app.post('/ui/focus', async (request) => {
    const body = request.body as { panel_id: string }
    const cmd = enqueueCommand(getKey(), {
      type: 'focus_panel',
      payload: { panel_id: body.panel_id },
    })
    return { ok: true, command: cmd }
  })
}
