/**
 * GitHub App HTTP routes — OAuth, installations, credential provisioning.
 * Mirrors Python's github_auth/router.py while keeping the newer `/github/*`
 * paths alive for smoke coverage.
 */
import { randomUUID } from 'node:crypto'
import type { FastifyInstance, FastifyReply, FastifyRequest } from 'fastify'
import { createAuthHook } from '../auth/middleware.js'
import {
  isGitHubConfigured,
  buildGitHubAppInstallationUrl,
  buildOAuthUrl,
  exchangeOAuthCode,
  getInstallationToken,
  listInstallations,
  listInstallationRepos,
  listUserInstallations,
  getGitCredentialsForInstallation,
  createGitHubAppJwt,
} from '../services/githubImpl.js'
import {
  getWorkspacePersistence,
  SettingsKeyRequiredError,
} from '../services/workspacePersistence.js'
import { resetLocalWorkspaceStore } from '../services/localWorkspaceStore.js'

interface PendingGitHubState {
  callback: string | null
  workspaceId: string | null
  createdAt: number
}

interface GitHubCallbackResult {
  success: boolean
  error: string | null
  installation_id?: number
  default_installation_id?: number | null
  installations?: Array<{ id: number; account: string }>
  install_url?: string
  message?: string
}

const pendingGitHubStates = new Map<string, PendingGitHubState>()
const STATE_TTL_MS = 10 * 60 * 1000 // 10 minutes

function pruneStaleStates(): void {
  const cutoff = Date.now() - STATE_TTL_MS
  for (const [key, value] of pendingGitHubStates) {
    if (value.createdAt < cutoff) pendingGitHubStates.delete(key)
  }
}

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function requestOrigin(request: FastifyRequest, app: FastifyInstance): string {
  if (app.config.publicAppOrigin) {
    return app.config.publicAppOrigin
  }
  const proto = String(request.headers['x-forwarded-proto'] || request.protocol || 'http')
  const host = String(
    request.headers['x-forwarded-host']
      || request.headers.host
      || request.hostname,
  )
  return `${proto}://${host}`
}

function callbackPathForAuthorizeRequest(request: FastifyRequest): string {
  const path = String(request.url || '').split('?', 1)[0]
  if (path.includes('/auth/github/authorize')) {
    return '/api/v1/auth/github/callback'
  }
  return '/api/v1/github/oauth/callback'
}

function buildCallbackHtml(result: GitHubCallbackResult, redirectTo: string): string {
  const message = result.success
    ? 'Connected successfully!'
    : result.message || result.error || 'Authorization failed.'
  const resultJson = JSON.stringify(result).replaceAll('<', '\\u003c')

  return `<!DOCTYPE html>
<html>
<head><title>GitHub Authorization</title></head>
<body>
<p>${escapeHtml(message)}</p>
<p>Redirecting...</p>
<script>
  const result = ${resultJson};
  try {
    if (result.install_url) {
      window.location.href = result.install_url;
    } else if (window.opener) {
      window.opener.postMessage({
        type: 'github-callback',
        ...result
      }, window.location.origin);
      setTimeout(function () { window.close(); }, 1000);
    } else {
      window.location.href = ${JSON.stringify(redirectTo)};
    }
  } catch (error) {
    window.location.href = ${JSON.stringify(redirectTo)};
  }
</script>
</body>
</html>`
}

function requireGitHubConfig(app: FastifyInstance, reply: FastifyReply): { appId: string; privateKey: string } | null {
  const { githubAppId, githubAppPrivateKey } = app.config
  if (!githubAppId || !githubAppPrivateKey || !isGitHubConfigured(app.config)) {
    void reply.code(503).send({ error: 'GitHub App not configured' })
    return null
  }
  return {
    appId: githubAppId,
    privateKey: githubAppPrivateKey,
  }
}

function isTruthyFlag(value: unknown): boolean {
  return String(value || '').trim().toLowerCase() === 'true'
    || String(value || '').trim() === '1'
}

export function resetGitHubRouteStateForTests(): void {
  pendingGitHubStates.clear()
  resetLocalWorkspaceStore()
}

export async function registerGitHubRoutes(app: FastifyInstance): Promise<void> {
  app.addHook('onRequest', createAuthHook(app))

  const config = app.config
  const persistence = getWorkspacePersistence(config)

  const statusHandler = async (request: FastifyRequest) => {
    const query = request.query as { workspace_id?: string }
    const link = request.sessionUserId
      ? await persistence.getUserGitHubLink(request.sessionUserId, request.sessionEmail)
      : { account_linked: false, default_installation_id: null }
    const connection = query.workspace_id
      ? await persistence.getWorkspaceGitHubConnection(query.workspace_id)
      : null

    return {
      ok: true,
      configured: isGitHubConfigured(config),
      app_slug: config.githubAppSlug || null,
      account_linked: link.account_linked || !!connection?.installation_id,
      default_installation_id: link.default_installation_id,
      connected: !!connection?.installation_id,
      installation_connected: !!connection?.installation_id,
      installation_id: connection?.installation_id ?? null,
      repo_selected: !!(connection?.installation_id && connection?.repo_url),
      repo_url: connection?.repo_url ?? null,
    }
  }

  for (const path of ['/github/status', '/auth/github/status']) {
    app.get(path, statusHandler)
  }

  const authorizeHandler = async (request: FastifyRequest, reply: FastifyReply) => {
    const query = request.query as {
      redirect_uri?: string
      workspace_id?: string
      force_install?: string | boolean
    }

    if (!config.githubAppClientId && !config.githubAppSlug) {
      return reply.code(503).send({ error: 'GitHub App authorize flow not configured' })
    }

    const state = randomUUID()
    const callbackUrl = query.redirect_uri?.trim()
      || `${requestOrigin(request, app)}${callbackPathForAuthorizeRequest(request)}`
    pruneStaleStates()
    pendingGitHubStates.set(state, {
      callback: callbackUrl,
      workspaceId: query.workspace_id?.trim() || null,
      createdAt: Date.now(),
    })

    const forceInstall = isTruthyFlag(query.force_install)
    let url: string
    if (!forceInstall && config.githubAppClientId) {
      url = buildOAuthUrl(config.githubAppClientId, callbackUrl, state)
    } else if (config.githubAppSlug) {
      url = buildGitHubAppInstallationUrl(config.githubAppSlug, state)
    } else if (config.githubAppClientId) {
      url = buildOAuthUrl(config.githubAppClientId, callbackUrl, state)
    } else {
      return reply.code(503).send({ error: 'GitHub App authorize flow not configured' })
    }

    return reply.redirect(url)
  }

  for (const path of ['/github/oauth/initiate', '/auth/github/authorize']) {
    app.get(path, authorizeHandler)
  }

  const callbackHandler = async (request: FastifyRequest, reply: FastifyReply) => {
    const query = request.query as {
      code?: string
      state?: string
      installation_id?: string | number
      setup_action?: string
      workspace_id?: string
    }

    const pending = query.state ? (pendingGitHubStates.get(String(query.state)) || null) : null
    if (query.state) {
      pendingGitHubStates.delete(String(query.state))
    }

    const workspaceId = pending?.workspaceId || String(query.workspace_id || '').trim() || null
    const redirectTo = workspaceId
      ? `${requestOrigin(request, app)}/w/${encodeURIComponent(workspaceId)}/settings`
      : requestOrigin(request, app)

    const result: GitHubCallbackResult = {
      success: false,
      error: null,
    }

    try {
      if (query.code) {
        if (!query.state || !pending) {
          result.error = 'Invalid or expired OAuth state'
        } else if (!config.githubAppClientId || !config.githubAppClientSecret) {
          result.error = 'GitHub App OAuth not configured'
        } else {
          const oauth = await exchangeOAuthCode(
            config.githubAppClientId,
            config.githubAppClientSecret,
            String(query.code),
          )
          if (!oauth.access_token) {
            result.error = 'No access token received'
          } else {
            const installations = await listUserInstallations(oauth.access_token)
            if (installations.length > 0) {
              const selectedInstallationId = installations[0].id
              const defaultInstallationId = installations.length === 1
                ? selectedInstallationId
                : null

              if (request.sessionUserId) {
                await persistence.setUserGitHubLink(
                  request.sessionUserId,
                  request.sessionEmail,
                  defaultInstallationId,
                )
              }

              if (workspaceId) {
                await persistence.setWorkspaceGitHubConnection(workspaceId, {
                  installation_id: selectedInstallationId,
                })
                result.success = true
                result.installation_id = selectedInstallationId
              } else {
                result.success = true
                result.default_installation_id = defaultInstallationId
                result.installations = installations.map((installation) => ({
                  id: installation.id,
                  account: installation.account,
                }))
              }
            } else if (workspaceId && config.githubAppSlug) {
              const installState = randomUUID()
              pendingGitHubStates.set(installState, {
                callback: pending.callback,
                workspaceId,
                createdAt: Date.now(),
              })
              result.install_url = buildGitHubAppInstallationUrl(config.githubAppSlug, installState)
              result.message = 'Install the GitHub App to continue.'
            } else {
              result.error = 'No installations found. Please install the GitHub App first.'
            }
          }
        }
      } else if (query.installation_id && query.setup_action) {
        const installationId = Number(query.installation_id)
        if (!Number.isInteger(installationId) || installationId <= 0) {
          result.error = 'Invalid installation_id'
        } else {
          if (workspaceId) {
            await persistence.setWorkspaceGitHubConnection(workspaceId, {
              installation_id: installationId,
            })
          }
          if (request.sessionUserId) {
            await persistence.setUserGitHubLink(
              request.sessionUserId,
              request.sessionEmail,
              installationId,
            )
          }
          result.success = true
          result.installation_id = installationId
        }
      } else {
        result.error = 'Missing code or installation_id'
      }
    } catch (error) {
      if (error instanceof SettingsKeyRequiredError) {
        result.error = 'Settings encryption key not configured'
      } else {
        result.error = error instanceof Error ? error.message : String(error)
      }
    }

    return reply
      .type('text/html; charset=utf-8')
      .send(buildCallbackHtml(result, redirectTo))
  }

  for (const path of ['/github/oauth/callback', '/auth/github/callback']) {
    app.get(path, callbackHandler)
  }

  const installationsHandler = async (_request: FastifyRequest, reply: FastifyReply) => {
    const configured = requireGitHubConfig(app, reply)
    if (!configured) {
      return reply
    }

    const installations = await listInstallations(
      configured.appId,
      configured.privateKey,
    )
    return { ok: true, installations }
  }

  for (const path of ['/github/installations', '/auth/github/installations']) {
    app.get(path, installationsHandler)
  }

  const connectHandler = async (request: FastifyRequest, reply: FastifyReply) => {
    const configured = requireGitHubConfig(app, reply)
    if (!configured) {
      return reply
    }

    const body = request.body as {
      workspace_id?: string
      installation_id?: number | string
      repo_url?: string
    } | null
    const workspaceId = String(body?.workspace_id || '').trim()
    const installationId = Number(body?.installation_id)
    const repoUrl = typeof body?.repo_url === 'string' && body.repo_url.trim()
      ? body.repo_url.trim()
      : undefined

    if (!workspaceId || !Number.isInteger(installationId) || installationId <= 0) {
      return reply.code(400).send({
        error: 'validation',
        message: 'workspace_id and installation_id are required',
      })
    }

    try {
      const appJwt = await createGitHubAppJwt(
        configured.appId,
        configured.privateKey,
      )
      await getInstallationToken(installationId, appJwt)
    } catch (error) {
      return reply.code(400).send({
        error: 'validation',
        message: `Invalid installation: ${error instanceof Error ? error.message : String(error)}`,
      })
    }

    try {
      await persistence.setWorkspaceGitHubConnection(workspaceId, {
        installation_id: installationId,
        ...(repoUrl ? { repo_url: repoUrl } : {}),
      })
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

    if (request.sessionUserId) {
      await persistence.setUserGitHubLink(
        request.sessionUserId,
        request.sessionEmail,
        installationId,
      )
    }

    return { ok: true, connected: true, installation_id: installationId }
  }

  for (const path of ['/github/connect', '/auth/github/connect']) {
    app.post(path, connectHandler)
  }

  const selectRepoHandler = async (request: FastifyRequest, reply: FastifyReply) => {
    const body = request.body as { workspace_id?: string; repo_url?: string } | null
    const workspaceId = String(body?.workspace_id || '').trim()
    const repoUrl = String(body?.repo_url || '').trim()

    if (!workspaceId || !repoUrl) {
      return reply.code(400).send({
        error: 'validation',
        message: 'workspace_id and repo_url are required',
      })
    }

    try {
      await persistence.setWorkspaceGitHubConnection(workspaceId, { repo_url: repoUrl })
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

    return {
      ok: true,
      repo_selected: true,
      repo_url: repoUrl,
    }
  }

  for (const path of ['/github/repo', '/auth/github/repo']) {
    app.post(path, selectRepoHandler)
  }

  const reposHandler = async (request: FastifyRequest, reply: FastifyReply) => {
    const configured = requireGitHubConfig(app, reply)
    if (!configured) {
      return reply
    }

    const query = request.query as { installation_id?: string | number }
    const installationId = Number(query.installation_id)
    if (!Number.isInteger(installationId) || installationId <= 0) {
      return reply.code(400).send({
        error: 'validation',
        message: 'installation_id is required',
      })
    }

    const repos = await listInstallationRepos(
      installationId,
      configured.appId,
      configured.privateKey,
    )
    return { ok: true, repos }
  }

  for (const path of ['/github/repos', '/auth/github/repos']) {
    app.get(path, reposHandler)
  }

  const credentialsHandler = async (request: FastifyRequest, reply: FastifyReply) => {
    const configured = requireGitHubConfig(app, reply)
    if (!configured) {
      return reply
    }

    const query = request.query as { workspace_id?: string }
    const workspaceId = String(query.workspace_id || '').trim()
    if (!workspaceId) {
      return reply.code(400).send({
        error: 'validation',
        message: 'workspace_id is required',
      })
    }

    const connection = await persistence.getWorkspaceGitHubConnection(workspaceId)
    if (!connection?.installation_id) {
      return reply.code(404).send({
        error: 'not_found',
        message: 'Workspace not connected to GitHub',
      })
    }

    const credentials = await getGitCredentialsForInstallation(
      connection.installation_id,
      configured.appId,
      configured.privateKey,
    )
    return credentials
  }

  for (const path of ['/github/git-credentials', '/auth/github/git-credentials']) {
    app.get(path, credentialsHandler)
  }

  const disconnectHandler = async (request: FastifyRequest, reply: FastifyReply) => {
    const body = request.body as { workspace_id?: string } | null
    const workspaceId = String(body?.workspace_id || '').trim()
    if (!workspaceId) {
      return reply.code(400).send({
        error: 'validation',
        message: 'workspace_id is required',
      })
    }

    try {
      await persistence.clearWorkspaceGitHubConnection(workspaceId)
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

    return { ok: true, disconnected: true }
  }

  for (const path of ['/github/disconnect', '/auth/github/disconnect']) {
    app.post(path, disconnectHandler)
  }
}
