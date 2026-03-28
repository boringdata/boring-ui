import { describe, it, expect } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'

const SERVER_ROOT = path.resolve(__dirname, '..')
const SHARED_ROOT = path.resolve(__dirname, '../../shared')

describe('Service layer skeleton structure', () => {
  // Service interface files (factories removed, interfaces kept)
  const expectedServiceFiles = [
    'services/files.ts',
    'services/git.ts',
    'services/exec.ts',
    'services/auth.ts',
    'services/workspaces.ts',
    'services/users.ts',
    'services/capabilities.ts',
    'services/approval.ts',
    'services/uiState.ts',
    'services/github.ts',
    'services/index.ts',
  ]

  // Active HTTP route files (*Routes.ts pattern)
  const expectedHttpFiles = [
    'http/health.ts',
    'http/fileRoutes.ts',
    'http/gitRoutes.ts',
    'http/authRoutes.ts',
    'http/workspaceRoutes.ts',
    'http/execRoutes.ts',
    'http/meRoutes.ts',
    'http/static.ts',
    'http/workspaceBoundary.ts',
    'http/uiStateRoutes.ts',
  ]

  // tRPC: only framework.ts (child app extension) remains
  const expectedTrpcFiles = [
    'trpc/framework.ts',
  ]

  const expectedAdapterFiles = ['adapters/bwrapImpl.ts']

  const expectedAuthFiles = [
    'auth/session.ts',
    'auth/neonClient.ts',
    'auth/middleware.ts',
    'auth/validation.ts',
  ]

  const expectedWorkspaceFiles = [
    'workspace/paths.ts',
    'workspace/boundary.ts',
    'workspace/helpers.ts',
  ]

  it.each(expectedServiceFiles)('services/%s exists', (file) => {
    expect(fs.existsSync(path.join(SERVER_ROOT, file))).toBe(true)
  })

  it.each(expectedHttpFiles)('http/%s exists', (file) => {
    expect(fs.existsSync(path.join(SERVER_ROOT, file))).toBe(true)
  })

  it.each(expectedTrpcFiles)('trpc/%s exists', (file) => {
    expect(fs.existsSync(path.join(SERVER_ROOT, file))).toBe(true)
  })

  it.each(expectedAdapterFiles)('adapters/%s exists', (file) => {
    expect(fs.existsSync(path.join(SERVER_ROOT, file))).toBe(true)
  })

  it.each(expectedAuthFiles)('auth/%s exists', (file) => {
    expect(fs.existsSync(path.join(SERVER_ROOT, file))).toBe(true)
  })

  it.each(expectedWorkspaceFiles)('workspace/%s exists', (file) => {
    expect(fs.existsSync(path.join(SERVER_ROOT, file))).toBe(true)
  })

  it('shared/types.ts exists', () => {
    expect(fs.existsSync(path.join(SHARED_ROOT, 'types.ts'))).toBe(true)
  })
})

describe('Service layer transport independence', () => {
  const serviceFiles = [
    'services/files.ts',
    'services/git.ts',
    'services/exec.ts',
    'services/auth.ts',
    'services/workspaces.ts',
    'services/users.ts',
    'services/capabilities.ts',
    'services/approval.ts',
    'services/uiState.ts',
    'services/github.ts',
  ]

  it.each(serviceFiles)(
    '%s has no Fastify or tRPC imports',
    (file) => {
      const content = fs.readFileSync(path.join(SERVER_ROOT, file), 'utf-8')
      expect(content).not.toMatch(/from\s+['"]fastify/)
      expect(content).not.toMatch(/from\s+['"]@trpc/)
      expect(content).not.toMatch(/from\s+['"]@fastify/)
    },
  )

  it('shared/types.ts has no server framework imports', () => {
    const content = fs.readFileSync(
      path.join(SHARED_ROOT, 'types.ts'),
      'utf-8',
    )
    expect(content).not.toMatch(/from\s+['"]fastify/)
    expect(content).not.toMatch(/from\s+['"]@trpc/)
    expect(content).not.toMatch(/from\s+['"]react/)
  })
})

describe('Service barrel exports active implementations', () => {
  it('exports real implementation factories', async () => {
    const barrel = await import('../services/index.js')
    expect(typeof barrel.createGitServiceImpl).toBe('function')
    expect(typeof barrel.buildCapabilitiesResponse).toBe('function')
    expect(typeof barrel.buildPythonCompatCapabilities).toBe('function')
    expect(typeof barrel.buildRuntimeConfigPayload).toBe('function')
    expect(typeof barrel.createGitHubAppJwt).toBe('function')
    expect(typeof barrel.buildGitCredentials).toBe('function')
    expect(typeof barrel.isGitHubConfigured).toBe('function')
  })

  it('service stubs no longer export throwing factories', async () => {
    // Verify factories were removed — only type exports remain
    const files = await import('../services/files.js')
    expect((files as any).createFileService).toBeUndefined()

    const git = await import('../services/git.js')
    expect((git as any).createGitService).toBeUndefined()
  })
})

describe('tRPC framework (child app extension)', () => {
  it('exports createFrameworkTRPC', async () => {
    const fw = await import('../trpc/framework.js')
    expect(typeof fw.createFrameworkTRPC).toBe('function')
    expect(typeof fw.mergeChildRouters).toBe('function')
    expect(typeof fw.registerChildTools).toBe('function')
  })
})

describe('auth/session exports', () => {
  it('exports COOKIE_NAME and appCookieName', async () => {
    const session = await import('../auth/session.js')
    expect(session.COOKIE_NAME).toBe('boring_session')
    expect(session.appCookieName('myapp')).toBe('boring_session_myapp')
    expect(session.appCookieName()).toBe('boring_session')
  })
})

describe('workspace/boundary exports', () => {
  it('exports WORKSPACE_PASSTHROUGH_PREFIXES', async () => {
    const boundary = await import('../workspace/boundary.js')
    expect(boundary.WORKSPACE_PASSTHROUGH_PREFIXES).toContain('/auth/')
    expect(boundary.WORKSPACE_PASSTHROUGH_PREFIXES).toContain('/api/v1/files')
    expect(boundary.WORKSPACE_PASSTHROUGH_PREFIXES).toContain('/api/v1/agent')
  })
})
