/**
 * User identity routes — GET /api/v1/me, GET/PUT /api/v1/me/settings.
 * Mirrors Python's me_router_neon.py.
 */
import type { FastifyInstance } from 'fastify'
import { createAuthHook } from '../auth/middleware.js'
import { getWorkspacePersistence } from '../services/workspacePersistence.js'

export async function registerMeRoutes(app: FastifyInstance): Promise<void> {
  const persistence = getWorkspacePersistence(app.config)

  // Auth hook for all routes in this plugin
  app.addHook('onRequest', createAuthHook(app))

  // GET /me — current user info
  app.get('/me', async (request) => {
    const stored = await persistence.getUserSettings(
      request.sessionUserId!,
      request.sessionEmail,
    )
    return {
      ok: true,
      user: {
        id: request.sessionUserId,
        email: request.sessionEmail,
        display_name: stored.display_name || request.sessionEmail?.split('@')[0] || 'User',
      },
    }
  })

  // GET /me/settings — user settings
  // Python compat: display_name appears in BOTH settings dict and top-level
  app.get('/me/settings', async (request) => {
    const stored = await persistence.getUserSettings(
      request.sessionUserId!,
      request.sessionEmail,
    )
    const displayName = stored.display_name || request.sessionEmail?.split('@')[0] || 'User'
    return {
      ok: true,
      settings: { ...stored.settings, display_name: displayName },
      display_name: displayName,
    }
  })

  // PUT /me/settings — update user settings
  app.put('/me/settings', async (request, reply) => {
    const body = request.body as Record<string, unknown> | null
    if (!body || typeof body !== 'object') {
      return reply.code(400).send({
        error: 'validation',
        message: 'Request body must be an object',
      })
    }

    const displayName = typeof body.display_name === 'string' ? body.display_name : undefined

    // Separate display_name from settings
    const { display_name: _, ...settingsUpdate } = body as any
    const updated = await persistence.putUserSettings(
      request.sessionUserId!,
      request.sessionEmail,
      {
      ...(displayName !== undefined ? { display_name: displayName } : {}),
      settings: settingsUpdate,
      },
    )

    return {
      ok: true,
      settings: updated.settings,
      display_name: updated.display_name,
    }
  })
}
