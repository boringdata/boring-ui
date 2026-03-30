/**
 * Server configuration — mirrors Python's APIConfig with Zod validation.
 * Reads from environment variables with sensible defaults.
 * Fail-closed: missing critical config crashes on startup with clear errors.
 */
import { randomBytes } from 'node:crypto'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { parse } from 'smol-toml'

// --- Types ---

export type WorkspaceBackend = 'bwrap' | 'lightningfs' | 'justbash'
export type AgentRuntime = 'pi' | 'ai-sdk'
export type AgentPlacement = 'browser' | 'server'
export type ControlPlaneProvider = 'local' | 'neon'

export interface ServerConfig {
  /** App identifier from boring.app.toml */
  appId: string
  /** App display name from boring.app.toml */
  appName: string
  /** App logo glyph from boring.app.toml */
  appLogo: string
  /** HTTP port (default: 8000) */
  port: number
  /** Bind host (default: 0.0.0.0) */
  host: string
  /** PostgreSQL connection URL */
  databaseUrl: string | undefined
  /** CORS allowed origins */
  corsOrigins: string[]
  /** Workspace root directory */
  workspaceRoot: string
  /** Session signing secret (auto-generated if not set) */
  sessionSecret: string
  /** Settings encryption key */
  settingsKey: string | undefined
  /** Neon Auth base URL */
  neonAuthBaseUrl: string | undefined
  /** Neon Auth JWKS URL */
  neonAuthJwksUrl: string | undefined
  /** Control plane provider: local | neon */
  controlPlaneProvider: ControlPlaneProvider
  /** Workspace backend: bwrap | lightningfs | justbash */
  workspaceBackend: WorkspaceBackend
  /** Agent runtime: pi | ai-sdk */
  agentRuntime: AgentRuntime
  /** Agent placement: browser | server */
  agentPlacement: AgentPlacement
  /** Agents mode: frontend | backend */
  agentsMode: string
  /** Custom agent system prompt from boring.app.toml [agent].system_prompt */
  agentSystemPrompt: string | undefined
  /** Public application origin (validated URL) */
  publicAppOrigin: string | undefined
  /** GitHub App ID */
  githubAppId: string | undefined
  /** GitHub App client ID */
  githubAppClientId: string | undefined
  /** GitHub App client secret */
  githubAppClientSecret: string | undefined
  /** GitHub App private key (PEM) */
  githubAppPrivateKey: string | undefined
  /** GitHub App slug (validated) */
  githubAppSlug: string | undefined
  /** GitHub sync enabled */
  githubSyncEnabled: boolean
  /** Auth session TTL in seconds */
  authSessionTtlSeconds: number
  /** Auth session cookie name */
  authSessionCookieName: string
  /** Set Secure flag on session cookies (HTTPS only) */
  authSessionSecureCookie: boolean
  /** Auth email provider */
  authEmailProvider: string
  /** Auth app name */
  authAppName: string
  /** Control plane app ID */
  controlPlaneAppId: string
  /** Fly.io API token */
  flyApiToken: string | undefined
  /** Fly.io workspace app */
  flyWorkspaceApp: string | undefined
  /** Static file directory for serving built frontend (optional) */
  staticDir: string | undefined
  /** Frontend feature flags from boring.app.toml */
  frontendFeatures: Record<string, unknown>
  /** Frontend panel config from boring.app.toml */
  frontendPanels: Record<string, unknown>
}

// --- Constants ---

const GITHUB_SLUG_RE = /^[A-Za-z0-9][A-Za-z0-9-]*$/
const PUBLIC_ORIGIN_RE = /^(https?):\/\/([^/]+)$/
const VALID_WORKSPACE_BACKENDS: WorkspaceBackend[] = ['bwrap', 'lightningfs', 'justbash']
const VALID_AGENT_RUNTIMES: AgentRuntime[] = ['pi', 'ai-sdk']
const VALID_AGENT_PLACEMENTS: AgentPlacement[] = ['browser', 'server']
const GENERATED_SESSION_SECRET_WARNING =
  'BORING_UI_SESSION_SECRET and BORING_SESSION_SECRET are unset; generated an ephemeral session secret. Existing sessions will not survive process restart.'

const DEFAULT_CORS_ORIGINS = [
  'http://localhost:5173',
  'http://localhost:5174',
  'http://localhost:5175',
  'http://localhost:5176',
  'http://localhost:3000',
  'http://127.0.0.1:5173',
  'http://127.0.0.1:5174',
  'http://127.0.0.1:5175',
  'http://127.0.0.1:5176',
]

let warnedAboutGeneratedSessionSecret = false

interface ParsedAppToml {
  app?: {
    id?: string
    name?: string
    logo?: string
  }
  workspace?: {
    backend?: string
  }
  agent?: {
    runtime?: string
    placement?: string
    system_prompt?: string
  }
  auth?: {
    session_cookie?: string
    session_ttl?: number
  }
  frontend?: {
    branding?: {
      name?: string
      logo?: string
    }
    features?: Record<string, unknown>
    panels?: Record<string, unknown>
    data?: {
      backend?: string
    }
  }
}

// --- Helpers ---

function envStr(name: string, fallback: string): string {
  const value = process.env[name]
  if (value === undefined) return fallback
  const trimmed = value.trim()
  return trimmed || fallback
}

function envBool(name: string, fallback: boolean): boolean {
  const value = process.env[name]
  if (value === undefined) return fallback
  return ['1', 'true', 'yes', 'on'].includes(value.trim().toLowerCase())
}

function envInt(name: string, fallback: number): number {
  const raw = process.env[name]
  if (raw === undefined) return fallback
  const parsed = parseInt(raw.trim(), 10)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

function envOptionalMultiline(name: string): string | undefined {
  const value = process.env[name]
  if (!value?.trim()) return undefined
  return value.trim().replace(/\\n/g, '\n')
}

function parseCorsOrigins(envValue: string | undefined): string[] {
  if (!envValue) return DEFAULT_CORS_ORIGINS
  return envValue.split(',').map((o) => o.trim()).filter(Boolean)
}

function normalizeControlPlaneProvider(): ControlPlaneProvider {
  const explicit = process.env.CONTROL_PLANE_PROVIDER?.trim().toLowerCase()
  if (explicit === 'neon') return 'neon'
  if (explicit === 'local') return 'local'
  // Auto-detect: if NEON_AUTH_BASE_URL is set, use neon
  if (process.env.NEON_AUTH_BASE_URL) return 'neon'
  return 'local'
}

function normalizeAgentsMode(): string {
  const value = (
    process.env.BUI_AGENTS_MODE ||
    process.env.AGENTS_MODE ||
    'frontend'
  ).trim().toLowerCase()
  return value === 'backend' ? 'backend' : 'frontend'
}

function normalizePublicOrigin(raw: string | undefined): string | undefined {
  if (!raw?.trim()) return undefined
  const match = raw.trim().match(PUBLIC_ORIGIN_RE)
  if (!match) return undefined
  return `${match[1]}://${match[2]}`
}

function normalizeGithubSlug(raw: string | undefined): string | undefined {
  if (!raw?.trim()) return undefined
  return GITHUB_SLUG_RE.test(raw.trim()) ? raw.trim() : undefined
}

function normalizeEmailProvider(raw: string | undefined): string {
  const value = (raw || '').trim().toLowerCase()
  if (['smtp', 'resend', 'email'].includes(value)) return 'smtp'
  if (['none', 'disabled', 'off'].includes(value)) return 'none'
  return process.env.RESEND_API_KEY ? 'smtp' : 'unknown'
}

function generateSessionSecret(): string {
  return randomBytes(48).toString('base64url')
}

function warnAboutGeneratedSessionSecret(): void {
  if (warnedAboutGeneratedSessionSecret) return
  warnedAboutGeneratedSessionSecret = true
  console.warn(GENERATED_SESSION_SECRET_WARNING)
}

function readAppToml(): ParsedAppToml {
  const explicitPath = process.env.BUI_APP_TOML?.trim() || process.env.BORING_APP_TOML?.trim() || ''
  const candidate = explicitPath || path.join(process.cwd(), 'boring.app.toml')
  if (!candidate || !existsSync(candidate)) return {}

  try {
    const parsed = parse(readFileSync(candidate, 'utf8'))
    if (parsed && typeof parsed === 'object') {
      return parsed as ParsedAppToml
    }
  } catch {
    return {}
  }

  return {}
}

function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {}
  return value as Record<string, unknown>
}

function resolveWorkspaceBackendFallback(appToml: ParsedAppToml): WorkspaceBackend {
  const explicit = appToml.workspace?.backend?.trim().toLowerCase()
  if (explicit === 'bwrap' || explicit === 'lightningfs' || explicit === 'justbash') {
    return explicit
  }

  const frontendBackend = appToml.frontend?.data?.backend?.trim().toLowerCase()
  if (frontendBackend === 'http') return 'bwrap'
  if (frontendBackend === 'lightningfs' || frontendBackend === 'justbash') {
    return frontendBackend
  }

  return 'bwrap'
}

function resolveAgentRuntimeFallback(appToml: ParsedAppToml): AgentRuntime {
  const runtime = appToml.agent?.runtime?.trim().toLowerCase()
  return runtime === 'ai-sdk' ? 'ai-sdk' : 'pi'
}

function resolveAgentPlacementFallback(appToml: ParsedAppToml): AgentPlacement {
  const placement = appToml.agent?.placement?.trim().toLowerCase()
  return placement === 'server' ? 'server' : 'browser'
}

// --- Main ---

export function loadConfig(): ServerConfig {
  const appToml = readAppToml()
  const appId = appToml.app?.id?.trim() || 'boring-ui'
  const appName =
    appToml.frontend?.branding?.name?.trim() ||
    appToml.app?.name?.trim() ||
    'Boring UI'
  const appLogo =
    appToml.frontend?.branding?.logo?.trim() ||
    appToml.app?.logo?.trim() ||
    'B'

  // Session secret precedence: BORING_UI_SESSION_SECRET → BORING_SESSION_SECRET → auto-generate
  let sessionSecret = process.env.BORING_UI_SESSION_SECRET?.trim() || ''
  if (!sessionSecret) {
    sessionSecret = process.env.BORING_SESSION_SECRET?.trim() || ''
  }
  if (!sessionSecret) {
    warnAboutGeneratedSessionSecret()
    sessionSecret = generateSessionSecret()
  }

  return {
    appId,
    appName,
    appLogo,
    port: envInt('PORT', 8000),
    host: envStr('HOST', '0.0.0.0'),
    databaseUrl: process.env.DATABASE_URL,
    corsOrigins: parseCorsOrigins(process.env.CORS_ORIGINS),
    workspaceRoot:
      process.env.BORING_UI_WORKSPACE_ROOT ||
      process.env.BUI_WORKSPACE_ROOT ||
      process.env.WORKSPACE_ROOT ||
      process.cwd(),
    sessionSecret,
    settingsKey: process.env.BORING_SETTINGS_KEY,
    neonAuthBaseUrl: process.env.NEON_AUTH_BASE_URL,
    neonAuthJwksUrl: process.env.NEON_AUTH_JWKS_URL,
    controlPlaneProvider: normalizeControlPlaneProvider(),
    workspaceBackend: (
      envStr('WORKSPACE_BACKEND', resolveWorkspaceBackendFallback(appToml)) as WorkspaceBackend
    ),
    agentRuntime: (
      envStr('AGENT_RUNTIME', resolveAgentRuntimeFallback(appToml)) as AgentRuntime
    ),
    agentPlacement: (
      envStr('AGENT_PLACEMENT', resolveAgentPlacementFallback(appToml)) as AgentPlacement
    ),
    agentsMode: normalizeAgentsMode(),
    agentSystemPrompt: (process.env.AGENT_SYSTEM_PROMPT || appToml.agent?.system_prompt || '').trim() || undefined,
    publicAppOrigin: normalizePublicOrigin(
      process.env.BORING_UI_PUBLIC_ORIGIN || process.env.PUBLIC_APP_ORIGIN,
    ),
    githubAppId: process.env.GITHUB_APP_ID,
    githubAppClientId: process.env.GITHUB_APP_CLIENT_ID,
    githubAppClientSecret: process.env.GITHUB_APP_CLIENT_SECRET,
    githubAppPrivateKey: envOptionalMultiline('GITHUB_APP_PRIVATE_KEY'),
    githubAppSlug: normalizeGithubSlug(process.env.GITHUB_APP_SLUG),
    githubSyncEnabled: envBool('GITHUB_SYNC_ENABLED', true),
    authSessionTtlSeconds: envInt(
      'AUTH_SESSION_TTL_SECONDS',
      Number.isFinite(appToml.auth?.session_ttl) ? Number(appToml.auth?.session_ttl) : 86400,
    ),
    authSessionCookieName: envStr(
      'AUTH_SESSION_COOKIE_NAME',
      appToml.auth?.session_cookie?.trim() || 'boring_session',
    ),
    authSessionSecureCookie: envBool('AUTH_SESSION_SECURE_COOKIE', false),
    authEmailProvider: normalizeEmailProvider(
      process.env.AUTH_EMAIL_PROVIDER || process.env.NEON_AUTH_EMAIL_PROVIDER,
    ),
    authAppName: envStr('AUTH_APP_NAME', appName),
    controlPlaneAppId: envStr('CONTROL_PLANE_APP_ID', appId),
    flyApiToken: process.env.FLY_API_TOKEN,
    flyWorkspaceApp: process.env.FLY_WORKSPACE_APP,
    staticDir: process.env.BORING_UI_STATIC_DIR || undefined,
    frontendFeatures: asRecord(appToml.frontend?.features),
    frontendPanels: asRecord(appToml.frontend?.panels),
  }
}

/**
 * Validate config and fail closed on misconfiguration.
 * Call this at startup — throws with clear error messages.
 */
export function validateConfig(config: ServerConfig): void {
  const errors: string[] = []

  // Validate workspace.backend
  if (!VALID_WORKSPACE_BACKENDS.includes(config.workspaceBackend)) {
    errors.push(
      `Invalid workspace.backend "${config.workspaceBackend}". ` +
      `Must be one of: ${VALID_WORKSPACE_BACKENDS.join(', ')}`,
    )
  }

  // Validate agent.runtime
  if (!VALID_AGENT_RUNTIMES.includes(config.agentRuntime)) {
    errors.push(
      `Invalid agent.runtime "${config.agentRuntime}". ` +
      `Must be one of: ${VALID_AGENT_RUNTIMES.join(', ')}`,
    )
  }

  // Validate agent.placement
  if (!VALID_AGENT_PLACEMENTS.includes(config.agentPlacement)) {
    errors.push(
      `Invalid agent.placement "${config.agentPlacement}". ` +
      `Must be one of: ${VALID_AGENT_PLACEMENTS.join(', ')}`,
    )
  }

  // Neon mode requires DATABASE_URL and NEON_AUTH_BASE_URL
  if (config.controlPlaneProvider === 'neon') {
    if (!config.databaseUrl) {
      errors.push(
        'DATABASE_URL is required when CONTROL_PLANE_PROVIDER=neon. ' +
        'Set DATABASE_URL or switch to CONTROL_PLANE_PROVIDER=local.',
      )
    }
    if (!config.neonAuthBaseUrl) {
      errors.push(
        'NEON_AUTH_BASE_URL is required when CONTROL_PLANE_PROVIDER=neon. ' +
        'Set NEON_AUTH_BASE_URL or switch to CONTROL_PLANE_PROVIDER=local.',
      )
    }
  }

  // Server-side agent placement requires bwrap backend and database
  if (config.agentPlacement === 'server') {
    if (config.workspaceBackend !== 'bwrap') {
      errors.push(
        `agent.placement=server requires workspace.backend=bwrap, ` +
        `got "${config.workspaceBackend}".`,
      )
    }
    if (!config.databaseUrl) {
      errors.push(
        'agent.placement=server requires DATABASE_URL for workspace state.',
      )
    }
  }

  if (config.agentRuntime === 'ai-sdk' && config.agentPlacement !== 'server') {
    errors.push(
      `agent.runtime=ai-sdk requires agent.placement=server, ` +
      `got "${config.agentPlacement}".`,
    )
  }

  if (errors.length > 0) {
    throw new Error(
      `Configuration validation failed:\n${errors.map((e) => `  - ${e}`).join('\n')}`,
    )
  }
}
