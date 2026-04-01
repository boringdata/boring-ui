/**
 * Fastify application factory — mirrors Python's create_app() pattern.
 *
 * All dependencies are injectable for testing and customization.
 */
import Fastify, { type FastifyInstance, type FastifyRequest, type FastifyReply } from 'fastify'
import cors from '@fastify/cors'
import cookie from '@fastify/cookie'
import { loadConfig, validateConfig, type ServerConfig } from './config.js'
import { registerRequestIdHook } from './middleware/requestId.js'
import { PINO_REDACT_PATHS } from './middleware/secretRedaction.js'
import { createAuthHook } from './auth/middleware.js'
import { createSessionCookie, parseSessionCookie, appCookieName as sessionAppCookieName } from './auth/session.js'
import { registerHealthRoutes } from './http/health.js'
import { registerWorkspaceRoutes } from './http/workspaceRoutes.js'
import { registerFileRoutes } from './http/fileRoutes.js'
import { registerGitRoutes } from './http/gitRoutes.js'
import { registerExecRoutes } from './http/execRoutes.js'
import { registerMeRoutes } from './http/meRoutes.js'
import { registerWorkspaceBoundary } from './http/workspaceBoundary.js'
import { registerCollaborationRoutes } from './http/collaborationRoutes.js'
import { registerUiStateRoutes } from './http/uiStateRoutes.js'
import { registerGitHubRoutes } from './http/githubRoutes.js'
import { registerStaticRoutes } from './http/static.js'
import { registerAuthRoutes } from './http/authRoutes.js'
import { registerAiSdkRoutes } from './http/aiSdkRoutes.js'
import { registerPiRoutes } from './http/piRoutes.js'

// Extend Fastify types to include our custom properties
declare module 'fastify' {
  interface FastifyRequest {
    sessionUserId?: string
    sessionEmail?: string
  }
  interface FastifyInstance {
    config: ServerConfig
  }
}

export interface CreateAppOptions {
  config?: ServerConfig
  logger?: boolean
  /** Skip config validation (for tests) */
  skipValidation?: boolean
}

export function createApp(options: CreateAppOptions = {}): FastifyInstance {
  const config = options.config ?? loadConfig()

  // Validate config unless explicitly skipped (e.g., tests).
  // In production, index.ts validates first and exits on failure.
  // Here we warn as a safety net for callers using partial configs.
  if (!options.skipValidation) {
    try {
      validateConfig(config)
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      console.warn(`[boring-ui] Config validation warning: ${msg}`)
    }
  }

  const app = Fastify({
    logger: options.logger
      ? { redact: PINO_REDACT_PATHS }
      : false,
    bodyLimit: 16 * 1024 * 1024,
  })

  // Store config on app instance for route access
  app.decorate('config', config)

  // --- Plugins ---
  app.register(cors, {
    origin: config.corsOrigins,
    credentials: true,
    methods: ['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
  })

  app.register(cookie)

  // --- Request ID middleware ---
  app.register(registerRequestIdHook)

  // --- Local dev auto-login: set session cookie on every request if missing ---
  if (config.controlPlaneProvider === 'local') {
    const devCookieName = config.authSessionCookieName || sessionAppCookieName()
    const devAppId = config.appId || config.controlPlaneAppId || undefined
    let cachedDevToken: string | null = null

    app.addHook('onRequest', async (request, reply) => {
      // Skip if there's already a valid cookie
      const existing = request.cookies[devCookieName]
      if (existing) {
        try {
          await parseSessionCookie(existing, config.sessionSecret)
          return // Cookie is valid, nothing to do
        } catch {
          // Cookie is invalid/expired — replace it
        }
      }
      // Reuse cached token to avoid JWT signing on every request
      if (!cachedDevToken) {
        cachedDevToken = await createSessionCookie('dev-local', 'dev@local', config.sessionSecret, {
          ttlSeconds: config.authSessionTtlSeconds,
          appId: devAppId,
        })
      }
      const token = cachedDevToken
      // Set cookie on response so browser gets it
      reply.setCookie(devCookieName, token, {
        path: '/',
        httpOnly: true,
        sameSite: 'lax',
        secure: false,
        maxAge: config.authSessionTtlSeconds,
      })
      // Inject into current request so downstream hooks see it
      request.cookies[devCookieName] = token
    })
  }

  // --- Health, capabilities, config endpoints (public, no auth) ---
  app.register(registerHealthRoutes)

  // --- Auth routes (login/logout/session) ---
  app.register(registerAuthRoutes)

  // --- Authenticated API routes ---
  // All /api/v1/* routes require session authentication.
  // Each route plugin gets its own auth hook via createAuthHook(app).
  // File, git, exec, and UI state routes are wrapped in a scoped plugin
  // that adds the auth hook, so they don't need inline auth code.

  // File routes (require auth)
  app.register(async (scoped) => {
    scoped.addHook('onRequest', createAuthHook(app))
    scoped.register(registerFileRoutes)
  }, { prefix: '/api/v1' })

  // Git routes (require auth)
  app.register(async (scoped) => {
    scoped.addHook('onRequest', createAuthHook(app))
    scoped.register(registerGitRoutes)
  }, { prefix: '/api/v1' })

  // Exec routes (require auth)
  app.register(async (scoped) => {
    scoped.addHook('onRequest', createAuthHook(app))
    scoped.register(registerExecRoutes)
  }, { prefix: '/api/v1' })

  // Server-side agent routes.
  // In local dev mode, register ALL agent routes so the frontend can switch
  // via URL params (?agent_mode=backend) without restarting the server.
  // In production, only register routes matching the configured placement+runtime.
  const isLocalDev = config.controlPlaneProvider === 'local'
  const registerPi = isLocalDev || (config.agentPlacement === 'server' && config.agentRuntime === 'pi')
  const registerAiSdk = isLocalDev || (config.agentPlacement === 'server' && config.agentRuntime === 'ai-sdk')

  if (registerPi) {
    app.register(async (scoped) => {
      scoped.addHook('onRequest', createAuthHook(app))
      scoped.register(registerPiRoutes)
    }, { prefix: '/api/v1' })
  }

  if (registerAiSdk) {
    app.register(async (scoped) => {
      scoped.addHook('onRequest', createAuthHook(app))
      scoped.register(registerAiSdkRoutes)
    }, { prefix: '/api/v1' })
  }

  // UI State routes (require auth)
  app.register(async (scoped) => {
    scoped.addHook('onRequest', createAuthHook(app))
    scoped.register(registerUiStateRoutes)
  }, { prefix: '/api/v1' })

  // User identity routes (auth in plugin)
  app.register(registerMeRoutes, { prefix: '/api/v1' })

  // Workspace routes (auth in plugin)
  app.register(registerWorkspaceRoutes, { prefix: '/api/v1' })

  // Collaboration routes (auth in plugin)
  app.register(registerCollaborationRoutes, { prefix: '/api/v1' })

  // GitHub App routes (auth in plugin)
  app.register(registerGitHubRoutes, { prefix: '/api/v1' })

  // --- Workspace boundary routing (/w/{id}/*) ---
  app.register(registerWorkspaceBoundary)

  // --- Static file serving + SPA fallback (must be LAST) ---
  if (config.staticDir) {
    app.register(async (instance) => {
      await registerStaticRoutes(instance, config.staticDir!)
    })
  }

  return app
}
