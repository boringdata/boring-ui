/**
 * User identity routes — GET /api/v1/me, GET/PUT /api/v1/me/settings.
 * Mirrors Python's me_router_neon.py.
 */
import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify'
import { createAuthHook } from '../auth/middleware.js'

export async function registerMeRoutes(app: FastifyInstance): Promise<void> {
  // Auth hook for all routes in this plugin
  app.addHook('onRequest', createAuthHook(app))

  // GET /me — current user info
  app.get('/me', async (request) => {
    return {
      ok: true,
      user: {
        id: request.sessionUserId,
        email: request.sessionEmail,
        display_name: request.sessionEmail?.split('@')[0] || 'User',
      },
    }
  })

  // GET /me/settings — user settings
  app.get('/me/settings', async (request) => {
    // DB query will be added when database is available (bd-fus66)
    return {
      ok: true,
      settings: {},
      display_name: request.sessionEmail?.split('@')[0] || 'User',
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

    // DB upsert will be added when database is available
    return {
      ok: true,
      settings: body,
    }
  })
}
