/**
 * Auth middleware — Fastify onRequest hook that validates the boring_session cookie.
 * Populates request.sessionUserId and request.sessionEmail on success.
 *
 * IMPORTANT: Uses reply.send() + return to short-circuit the request lifecycle.
 * In Fastify, returning from an async hook after calling reply.send() prevents
 * the route handler from executing.
 */
import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify'
import { parseSessionCookie, appCookieName, SessionExpiredError } from './session.js'

/**
 * Create a Fastify onRequest hook that validates session cookies.
 * The hook reads the session secret and cookie name from app.config.
 *
 * Usage:
 *   app.addHook('onRequest', createAuthHook(app))
 */
export function createAuthHook(app: FastifyInstance) {
  const cookieName = app.config.authSessionCookieName || appCookieName()

  return async function authHook(
    request: FastifyRequest,
    reply: FastifyReply,
  ): Promise<void> {
    const token = request.cookies[cookieName]
    const secret = app.config.sessionSecret

    if (!token) {
      return reply.code(401).send({
        error: 'unauthorized',
        code: 'SESSION_REQUIRED',
        message: 'Authentication required',
      })
    }

    try {
      const session = await parseSessionCookie(token, secret)
      request.sessionUserId = session.user_id
      request.sessionEmail = session.email
    } catch (err) {
      if (err instanceof SessionExpiredError) {
        return reply.code(401).send({
          error: 'unauthorized',
          code: 'SESSION_EXPIRED',
          message: 'Session has expired. Please sign in again.',
        })
      }
      return reply.code(401).send({
        error: 'unauthorized',
        code: 'INVALID_SESSION',
        message: 'Invalid session',
      })
    }
  }
}
