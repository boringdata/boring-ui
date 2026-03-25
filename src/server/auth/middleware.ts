/**
 * Auth middleware — Fastify preHandler that validates the boring_session cookie.
 * Populates request.sessionUserId and request.sessionEmail on success.
 */
import type { FastifyRequest, FastifyReply } from 'fastify'
import { parseSessionCookie, appCookieName, SessionExpiredError, SessionInvalidError } from './session.js'

export interface AuthMiddlewareOptions {
  secret: string
  appId?: string
  /** If true, skip auth for specific paths (e.g., health checks) */
  excludePaths?: string[]
}

/**
 * Create a Fastify preHandler hook that validates session cookies.
 */
export function createAuthHook(options: AuthMiddlewareOptions) {
  const { secret, appId, excludePaths = [] } = options
  const cookieName = appCookieName(appId)

  return async function authHook(
    request: FastifyRequest,
    reply: FastifyReply,
  ): Promise<void> {
    // Skip auth for excluded paths
    if (excludePaths.some((p) => request.url.startsWith(p))) {
      return
    }

    const token = request.cookies[cookieName]

    if (!token) {
      reply.code(401).send({
        error: 'unauthorized',
        code: 'SESSION_REQUIRED',
        message: 'Authentication required',
      })
      return
    }

    try {
      const session = await parseSessionCookie(token, secret)
      request.sessionUserId = session.user_id
      request.sessionEmail = session.email
    } catch (err) {
      if (err instanceof SessionExpiredError) {
        reply.code(401).send({
          error: 'unauthorized',
          code: 'SESSION_EXPIRED',
          message: 'Session has expired. Please sign in again.',
        })
        return
      }
      reply.code(401).send({
        error: 'unauthorized',
        code: 'INVALID_SESSION',
        message: 'Invalid session',
      })
    }
  }
}
