/**
 * Workspace HTTP routes — CRUD, settings (pgp_sym_encrypt), runtime state.
 * Mirrors Python's workspace_router_hosted.py.
 *
 * All routes require authentication via session cookie.
 */
import type { FastifyInstance } from 'fastify'
import { createAuthHook } from '../auth/middleware.js'
import {
  getWorkspacePersistence,
  RuntimeInvalidTransitionError,
  RuntimeNotFoundError,
  SettingsKeyRequiredError,
} from '../services/workspacePersistence.js'
import { UUID_RE } from '../workspace/helpers.js'

function isValidUUID(value: string): boolean {
  return UUID_RE.test(value)
}

export async function registerWorkspaceRoutes(
  app: FastifyInstance,
): Promise<void> {
  const persistence = getWorkspacePersistence(app.config)

  // Auth hook for all routes in this plugin
  app.addHook('onRequest', createAuthHook(app))

  // --- LIST WORKSPACES ---
  app.get('/workspaces', async (request, reply) => {
    if (!request.sessionUserId) {
      return reply.code(401).send({ error: 'unauthorized' })
    }

    const workspaces = await persistence.listWorkspaces(request.sessionUserId)
    return {
      ok: true,
      workspaces: workspaces.map((w) => ({ ...w, workspace_id: w.id })),
      count: workspaces.length,
    }
  })

  // --- CREATE WORKSPACE ---
  app.post('/workspaces', async (request, reply) => {
    if (!request.sessionUserId) {
      return reply.code(401).send({ error: 'unauthorized' })
    }

    const body = request.body as { name?: string } | null
    const name =
      body?.name?.trim() ||
      `Workspace ${new Date().toISOString().slice(0, 16).replace('T', ' ')} UTC`

    if (name.length > 100) {
      return reply.code(400).send({
        error: 'validation',
        code: 'WORKSPACE_NAME_TOO_LONG',
        message: 'Workspace name must be 100 characters or less',
      })
    }

    const ws = await persistence.createWorkspace(
      request.sessionUserId,
      name,
    )
    reply.code(201)
    return {
      ok: true,
      workspace: { ...ws, workspace_id: ws.id },
    }
  })

  // --- GET WORKSPACE RUNTIME ---
  app.get<{ Params: { id: string } }>(
    '/workspaces/:id/runtime',
    async (request, reply) => {
      if (!request.sessionUserId) {
        return reply.code(401).send({ error: 'unauthorized' })
      }

      const { id } = request.params
      if (!isValidUUID(id)) {
        return reply.code(400).send({
          error: 'validation',
          code: 'INVALID_WORKSPACE_ID',
          message: 'Invalid workspace ID format',
        })
      }

      if (app.config.controlPlaneProvider === 'neon') {
        const workspace = await persistence.getWorkspace(id)
        if (!workspace) {
          return reply.code(404).send({
            error: 'not_found',
            code: 'WORKSPACE_NOT_FOUND',
            message: 'Workspace not found',
          })
        }
      }

      const runtime = await persistence.getWorkspaceRuntime(id)
      return {
        ok: true,
        runtime,
      }
    },
  )

  // --- UPDATE WORKSPACE ---
  app.patch<{ Params: { id: string } }>(
    '/workspaces/:id',
    async (request, reply) => {
      if (!request.sessionUserId) {
        return reply.code(401).send({ error: 'unauthorized' })
      }

      const { id } = request.params
      if (!isValidUUID(id)) {
        return reply.code(400).send({
          error: 'validation',
          code: 'INVALID_WORKSPACE_ID',
          message: 'Invalid workspace ID format',
        })
      }

      const body = request.body as { name?: string } | null
      if (!body?.name?.trim()) {
        return reply.code(400).send({
          error: 'validation',
          code: 'NAME_REQUIRED',
          message: 'Workspace name is required',
        })
      }

      if (body.name.length > 100) {
        return reply.code(400).send({
          error: 'validation',
          code: 'WORKSPACE_NAME_TOO_LONG',
          message: 'Workspace name must be 100 characters or less',
        })
      }

      const updated = await persistence.updateWorkspace(id, { name: body.name })
      if (!updated && app.config.controlPlaneProvider === 'neon') {
        return reply.code(404).send({
          error: 'not_found',
          code: 'WORKSPACE_NOT_FOUND',
          message: 'Workspace not found',
        })
      }

      return {
        ok: true,
        workspace: updated
          ? { ...updated, workspace_id: updated.id }
          : { id, workspace_id: id, name: body.name },
      }
    },
  )

  // --- DELETE WORKSPACE ---
  app.delete<{ Params: { id: string } }>(
    '/workspaces/:id',
    async (request, reply) => {
      if (!request.sessionUserId) {
        return reply.code(401).send({ error: 'unauthorized' })
      }

      const { id } = request.params
      if (!isValidUUID(id)) {
        return reply.code(400).send({
          error: 'validation',
          code: 'INVALID_WORKSPACE_ID',
          message: 'Invalid workspace ID format',
        })
      }

      const deleted = await persistence.deleteWorkspace(id)
      if (!deleted && app.config.controlPlaneProvider === 'neon') {
        return reply.code(404).send({
          error: 'not_found',
          code: 'WORKSPACE_NOT_FOUND',
          message: 'Workspace not found or already deleted',
        })
      }

      return { ok: true, deleted: true }
    },
  )

  // --- GET WORKSPACE SETTINGS ---
  app.get<{ Params: { id: string } }>(
    '/workspaces/:id/settings',
    async (request, reply) => {
      if (!request.sessionUserId) {
        return reply.code(401).send({ error: 'unauthorized' })
      }

      const { id } = request.params
      if (!isValidUUID(id)) {
        return reply.code(400).send({
          error: 'validation',
          code: 'INVALID_WORKSPACE_ID',
          message: 'Invalid workspace ID format',
        })
      }

      if (app.config.controlPlaneProvider === 'neon') {
        const workspace = await persistence.getWorkspace(id)
        if (!workspace) {
          return reply.code(404).send({
            error: 'not_found',
            code: 'WORKSPACE_NOT_FOUND',
            message: 'Workspace not found',
          })
        }
      }

      const settings = await persistence.getWorkspaceSettings(id)
      return {
        ok: true,
        settings,
        data: { workspace_settings: settings },
      }
    },
  )

  // --- UPDATE WORKSPACE SETTINGS ---
  app.put<{ Params: { id: string } }>(
    '/workspaces/:id/settings',
    async (request, reply) => {
      if (!request.sessionUserId) {
        return reply.code(401).send({ error: 'unauthorized' })
      }

      const { id } = request.params
      if (!isValidUUID(id)) {
        return reply.code(400).send({
          error: 'validation',
          code: 'INVALID_WORKSPACE_ID',
          message: 'Invalid workspace ID format',
        })
      }

      const body = request.body as Record<string, string> | null
      if (!body || typeof body !== 'object') {
        return reply.code(400).send({
          error: 'validation',
          code: 'SETTINGS_REQUIRED',
          message: 'Request body must be an object with key-value settings',
        })
      }

      const keys = Object.keys(body)
      if (keys.length > 50) {
        return reply.code(400).send({
          error: 'validation',
          code: 'TOO_MANY_SETTINGS',
          message: 'Maximum 50 settings per request',
        })
      }

      for (const key of keys) {
        if (!key || key.length > 128) {
          return reply.code(400).send({
            error: 'validation',
            code: 'INVALID_SETTING_KEY',
            message: `Setting key must be 1-128 characters: ${key}`,
          })
        }
        if (typeof body[key] !== 'string' || !body[key]) {
          return reply.code(400).send({
            error: 'validation',
            code: 'INVALID_SETTING_VALUE',
            message: `Setting value must be a non-empty string for key: ${key}`,
          })
        }
      }

      if (!app.config.settingsKey) {
        return reply.code(500).send({
          error: 'server_error',
          code: 'SETTINGS_KEY_NOT_CONFIGURED',
          message: 'Settings encryption key not configured',
        })
      }

      if (app.config.controlPlaneProvider === 'neon') {
        const workspace = await persistence.getWorkspace(id)
        if (!workspace) {
          return reply.code(404).send({
            error: 'not_found',
            code: 'WORKSPACE_NOT_FOUND',
            message: 'Workspace not found',
          })
        }
      }

      let updated
      try {
        updated = await persistence.putWorkspaceSettings(id, body)
      } catch (error) {
        if (error instanceof SettingsKeyRequiredError) {
          return reply.code(500).send({
            error: 'server_error',
            code: error.code,
            message: 'Settings encryption key not configured',
          })
        }
        throw error
      }

      return { ok: true, settings: updated }
    },
  )

  // --- RETRY WORKSPACE RUNTIME ---
  app.post<{ Params: { id: string } }>(
    '/workspaces/:id/runtime/retry',
    async (request, reply) => {
      if (!request.sessionUserId) {
        return reply.code(401).send({ error: 'unauthorized' })
      }

      const { id } = request.params
      if (!isValidUUID(id)) {
        return reply.code(400).send({
          error: 'validation',
          code: 'INVALID_WORKSPACE_ID',
          message: 'Invalid workspace ID format',
        })
      }

      let runtime
      try {
        runtime = await persistence.retryWorkspaceRuntime(id)
      } catch (error) {
        if (error instanceof RuntimeNotFoundError) {
          return reply.code(404).send({
            error: 'not_found',
            code: error.code,
            message: error.message,
          })
        }
        if (error instanceof RuntimeInvalidTransitionError) {
          return reply.code(409).send({
            error: 'conflict',
            code: error.code,
            message: error.message,
          })
        }
        throw error
      }

      return {
        ok: true,
        runtime,
        retried: true,
      }
    },
  )
}
