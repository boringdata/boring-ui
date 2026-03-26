/**
 * Auth routes — session login/logout for the TS server.
 *
 * In local mode: dev login bypass (no real auth)
 * In neon mode: delegates to Neon Auth (Phase 3)
 */
import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify'
import { createSessionCookie, appCookieName } from '../auth/session.js'

export async function registerAuthRoutes(app: FastifyInstance): Promise<void> {
  const config = app.config

  // --- Dev login (local mode only) ---
  // GET /auth/login?user_id=...&email=...&redirect_uri=/
  // Creates a session cookie and redirects. Used by smoke tests.
  if (config.controlPlaneProvider === 'local') {
    app.get('/auth/login', async (request: FastifyRequest, reply: FastifyReply) => {
      const query = request.query as {
        user_id?: string
        email?: string
        redirect_uri?: string
      }

      const userId = query.user_id || 'dev-user'
      const email = query.email || 'dev@localhost'
      const redirectUri = query.redirect_uri || '/'

      // Create session cookie
      const token = await createSessionCookie(
        userId,
        email,
        config.sessionSecret,
        { ttlSeconds: config.authSessionTtlSeconds, appId: config.controlPlaneAppId },
      )

      // Use the same cookie name as auth middleware (default: boring_session)
      const cookieName = config.authSessionCookieName || appCookieName()

      reply.setCookie(cookieName, token, {
        path: '/',
        httpOnly: true,
        sameSite: 'lax',
        maxAge: config.authSessionTtlSeconds,
      })

      return reply.redirect(redirectUri)
    })

    // GET /auth/session — check current session
    app.get('/auth/session', async (request: FastifyRequest, reply: FastifyReply) => {
      return {
        authenticated: !!request.sessionUserId,
        user_id: request.sessionUserId || null,
        email: request.sessionEmail || null,
      }
    })

    // POST /auth/logout — clear session cookie
    app.post('/auth/logout', async (_request: FastifyRequest, reply: FastifyReply) => {
      const cookieName = config.authSessionCookieName || appCookieName()
      reply.clearCookie(cookieName, { path: '/' })
      return { ok: true }
    })
  }
}
