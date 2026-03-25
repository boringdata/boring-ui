/**
 * GitHub App HTTP routes — OAuth, installations, credential provisioning.
 * Mirrors Python's github_auth/router.py.
 */
import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify'
import { createAuthHook } from '../auth/middleware.js'
import {
  isGitHubConfigured,
  buildOAuthUrl,
} from '../services/githubImpl.js'

export async function registerGitHubRoutes(app: FastifyInstance): Promise<void> {
  app.addHook('onRequest', createAuthHook(app))

  const config = app.config

  // GET /github/status — check if GitHub is configured
  app.get('/github/status', async () => {
    return {
      ok: true,
      configured: isGitHubConfigured(config),
      app_slug: config.githubAppSlug || null,
    }
  })

  // GET /github/oauth/initiate — start OAuth flow
  app.get('/github/oauth/initiate', async (request, reply) => {
    if (!config.githubAppClientId) {
      return reply.code(503).send({ error: 'GitHub App not configured' })
    }

    const state = crypto.randomUUID()
    const origin = config.publicAppOrigin || `${request.protocol}://${request.hostname}`
    const redirectUri = `${origin}/api/v1/github/oauth/callback`
    const url = buildOAuthUrl(config.githubAppClientId, redirectUri, state)

    return { ok: true, url, state }
  })

  // GET /github/oauth/callback — handle OAuth callback
  app.get('/github/oauth/callback', async (request, reply) => {
    const { code, state } = request.query as { code?: string; state?: string }
    if (!code) {
      return reply.code(400).send({ error: 'validation', message: 'code is required' })
    }
    // Full implementation requires exchangeOAuthCode + store connection
    return { ok: true, connected: true }
  })

  // GET /github/installations — list app installations
  app.get('/github/installations', async () => {
    if (!isGitHubConfigured(config)) {
      return { ok: true, installations: [] }
    }
    // Full implementation requires GitHub API call with App JWT
    return { ok: true, installations: [] }
  })

  // POST /github/disconnect — remove GitHub connection
  app.post('/github/disconnect', async () => {
    return { ok: true, disconnected: true }
  })
}
