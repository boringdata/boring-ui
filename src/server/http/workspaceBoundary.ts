/**
 * Workspace boundary router — maps /w/{workspaceId}/* to workspace-scoped routes.
 *
 * In the TS architecture, this sets ctx.workspaceId via middleware instead of
 * the Python ASGI proxy pattern. This eliminates transport indirection.
 */
import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify'
import {
  parseSessionCookie,
  appCookieName,
  SessionExpiredError,
} from '../auth/session.js'

declare module 'fastify' {
  interface FastifyRequest {
    workspaceId?: string
  }
}

// Allowed path prefixes for workspace-scoped passthrough
const PASSTHROUGH_PREFIXES = [
  '/api/v1/files',
  '/api/v1/git',
  '/api/v1/ui',
  '/api/v1/me',
  '/api/v1/workspaces',
  '/api/v1/exec',
  '/api/capabilities',
  '/api/config',
  '/api/project',
  '/api/approval',
]

// Paths that bypass workspace auth (served as SPA pages)
const SPA_PATHS = new Set(['', 'setup', 'settings'])

// UUID format
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export async function registerWorkspaceBoundary(
  app: FastifyInstance,
): Promise<void> {
  // Catch-all route for /w/:workspaceId/*
  app.all('/w/:workspaceId/*', async (request: FastifyRequest, reply: FastifyReply) => {
    const { workspaceId } = request.params as { workspaceId: string }

    if (!UUID_RE.test(workspaceId)) {
      return reply.code(400).send({
        error: 'validation',
        code: 'INVALID_WORKSPACE_ID',
        message: 'Invalid workspace ID',
      })
    }

    // Extract the remaining path after /w/{id}/
    const wildcard = (request.params as any)['*'] || ''

    // SPA pages — serve index.html for browser navigation
    if (SPA_PATHS.has(wildcard) && request.headers.accept?.includes('text/html')) {
      return reply.code(200).type('text/html').send('<!DOCTYPE html><html><body>SPA</body></html>')
    }

    // Validate that the path is an allowed passthrough
    const normalizedPath = '/' + wildcard.replace(/^\//, '')
    const isAllowed = PASSTHROUGH_PREFIXES.some((prefix) =>
      normalizedPath.startsWith(prefix),
    )

    if (!isAllowed) {
      return reply.code(404).send({
        error: 'not_found',
        code: 'ROUTE_NOT_FOUND',
        message: `Route not found: /w/${workspaceId}/${wildcard}`,
      })
    }

    // Set workspace ID on request for downstream handlers
    request.workspaceId = workspaceId

    // Auth check
    const cookieName = appCookieName()
    const token = request.cookies[cookieName]

    if (!token) {
      return reply.code(401).send({
        error: 'unauthorized',
        code: 'SESSION_REQUIRED',
        message: 'Authentication required',
      })
    }

    try {
      const session = await parseSessionCookie(token, app.config.sessionSecret)
      request.sessionUserId = session.user_id
      request.sessionEmail = session.email
    } catch (err) {
      if (err instanceof SessionExpiredError) {
        return reply.code(401).send({ error: 'unauthorized', code: 'SESSION_EXPIRED' })
      }
      return reply.code(401).send({ error: 'unauthorized', code: 'INVALID_SESSION' })
    }

    // Redirect to the actual route (strip /w/{id} prefix).
    // Uses 307 to preserve the HTTP method (302 would change POST→GET).
    // NOTE: POST/PUT redirects lose the request body in most clients.
    // The frontend sends API calls directly to /api/v1/* (not through /w/{id}/*),
    // so this redirect primarily serves GET requests and browser navigation.
    const queryStr = request.url.includes('?') ? '?' + request.url.split('?')[1] : ''
    reply.code(307)
    return reply.redirect(normalizedPath + queryStr)
  })

  // Workspace root — serve SPA
  app.get('/w/:workspaceId', async (request: FastifyRequest, reply: FastifyReply) => {
    return reply.code(200).type('text/html').send('<!DOCTYPE html><html><body>SPA</body></html>')
  })
}
