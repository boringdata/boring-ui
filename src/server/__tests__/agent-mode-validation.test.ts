/**
 * Agent mode validation — verifies the TS server is ready for the
 * canonical browser PI placement profile.
 *
 * Tests the server-side contract that browser PI depends on:
 * - Capabilities endpoint returns agent.chat + agent.tools
 * - File routes work (PI calls these via HTTP)
 * - Exec routes work (PI calls exec_bash via HTTP)
 * - Git routes work (PI calls git tools via HTTP)
 * - Config validation accepts bwrap + browser + pi
 * - Config validation rejects invalid combos
 */
import { describe, it, expect } from 'vitest'
import { createApp } from '../app.js'
import { loadConfig, validateConfig } from '../config.js'
import { testSessionCookie, TEST_SECRET } from './helpers.js'

describe('Agent mode: browser PI server-side contract', () => {
  function getApp(overrides: Record<string, unknown> = {}) {
    const config = { ...loadConfig(), sessionSecret: TEST_SECRET, ...overrides }
    return createApp({ config: config as any, skipValidation: true })
  }

  describe('Capabilities for browser PI', () => {
    it('returns agent.chat and agent.tools capabilities', async () => {
      const app = getApp()
      const res = await app.inject({ method: 'GET', url: '/api/capabilities' })
      expect(res.statusCode).toBe(200)
      const body = JSON.parse(res.payload)
      // Python-compat mode: check features
      const features = body.features || body.capabilities || {}
      // Browser PI needs chat + tool approval surface
      expect(features.chat_claude_code || features['agent.chat']).toBeTruthy()
      await app.close()
    })

    it('returns workspace.files capability for file tools', async () => {
      const app = getApp()
      const res = await app.inject({ method: 'GET', url: '/api/capabilities' })
      const body = JSON.parse(res.payload)
      const features = body.features || body.capabilities || {}
      expect(features.files || features['workspace.files']).toBeTruthy()
      await app.close()
    })

    it('returns workspace.exec capability for exec tools', async () => {
      const app = getApp()
      const res = await app.inject({ method: 'GET', url: '/api/capabilities' })
      const body = JSON.parse(res.payload)
      const features = body.features || body.capabilities || {}
      expect(features.exec || features['workspace.exec']).toBeTruthy()
      await app.close()
    })
  })

  describe('File tool endpoints (used by PI write_file/read_file)', () => {
    it('write + read roundtrip works', async () => {
      const app = getApp()
      const token = await testSessionCookie()
      const cookies = { boring_session: token }

      // Write file
      const writeRes = await app.inject({
        method: 'PUT',
        url: '/api/v1/files/write?path=agent-test.txt',
        cookies,
        payload: { content: 'hello from agent' },
      })
      expect(writeRes.statusCode).toBe(200)

      // Read back
      const readRes = await app.inject({
        method: 'GET',
        url: '/api/v1/files/read?path=agent-test.txt',
        cookies,
      })
      expect(readRes.statusCode).toBe(200)
      const body = JSON.parse(readRes.payload)
      expect(body.content).toBe('hello from agent')

      await app.close()
    })
  })

  describe('Exec tool endpoint (used by PI exec_bash)', () => {
    it('executes command and returns stdout', async () => {
      const app = getApp()
      const token = await testSessionCookie()

      const res = await app.inject({
        method: 'POST',
        url: '/api/v1/exec',
        cookies: { boring_session: token },
        payload: { command: 'echo "agent exec test"' },
      })
      expect(res.statusCode).toBe(200)
      const body = JSON.parse(res.payload)
      expect(body.stdout).toContain('agent exec test')
      expect(body.exit_code).toBe(0)

      await app.close()
    })
  })

  describe('Git tool endpoint (used by PI git_status)', () => {
    it('returns git status', async () => {
      const app = getApp()
      const token = await testSessionCookie()

      const res = await app.inject({
        method: 'GET',
        url: '/api/v1/git/status',
        cookies: { boring_session: token },
      })
      expect(res.statusCode).toBe(200)
      const body = JSON.parse(res.payload)
      expect(body).toHaveProperty('is_repo')
      expect(body).toHaveProperty('files')

      await app.close()
    })
  })

  describe('Runtime-specific server routes', () => {
    it('does not mount PI routes when ai-sdk runtime is selected', async () => {
      const app = getApp({
        workspaceBackend: 'bwrap',
        agentPlacement: 'server',
        agentRuntime: 'ai-sdk',
        databaseUrl: 'postgres://test',
        controlPlaneProvider: 'local',
      })

      const token = await testSessionCookie()
      const res = await app.inject({
        method: 'GET',
        url: '/api/v1/agent/pi/sessions',
        cookies: { boring_session: token },
      })

      expect(res.statusCode).toBe(404)
      await app.close()
    })

    it('mounts the ai-sdk chat endpoint and fails closed without a server API key', async () => {
      const app = getApp({
        workspaceBackend: 'bwrap',
        agentPlacement: 'server',
        agentRuntime: 'ai-sdk',
        databaseUrl: 'postgres://test',
        controlPlaneProvider: 'local',
      })

      const token = await testSessionCookie()
      const res = await app.inject({
        method: 'POST',
        url: '/api/v1/agent/chat',
        cookies: { boring_session: token },
        payload: { messages: [] },
      })

      expect(res.statusCode).toBe(503)
      expect(JSON.parse(res.payload)).toMatchObject({
        code: 'ANTHROPIC_API_KEY_REQUIRED',
      })
      await app.close()
    })
  })
})

describe('Config validation matrix', () => {
  it('accepts bwrap + browser + pi (foundation profile)', () => {
    const config = {
      ...loadConfig(),
      workspaceBackend: 'bwrap' as const,
      agentPlacement: 'browser' as const,
      agentRuntime: 'pi' as const,
      controlPlaneProvider: 'local' as const,
    }
    expect(() => validateConfig(config)).not.toThrow()
  })

  it('accepts lightningfs + browser (local dev)', () => {
    const config = {
      ...loadConfig(),
      workspaceBackend: 'lightningfs' as const,
      agentPlacement: 'browser' as const,
      agentRuntime: 'pi' as const,
      controlPlaneProvider: 'local' as const,
    }
    expect(() => validateConfig(config)).not.toThrow()
  })

  it('rejects server placement without bwrap', () => {
    const config = {
      ...loadConfig(),
      workspaceBackend: 'lightningfs' as const,
      agentPlacement: 'server' as const,
      agentRuntime: 'pi' as const,
      databaseUrl: 'postgres://test',
      controlPlaneProvider: 'local' as const,
    }
    expect(() => validateConfig(config)).toThrow(/placement.*server.*bwrap/)
  })

  it('accepts ai-sdk with server placement on bwrap', () => {
    const config = {
      ...loadConfig(),
      workspaceBackend: 'bwrap' as const,
      agentPlacement: 'server' as const,
      agentRuntime: 'ai-sdk' as const,
      databaseUrl: 'postgres://test',
      controlPlaneProvider: 'local' as const,
    }
    expect(() => validateConfig(config)).not.toThrow()
  })

  it('rejects ai-sdk runtime in browser placement', () => {
    const config = {
      ...loadConfig(),
      workspaceBackend: 'bwrap' as const,
      agentPlacement: 'browser' as const,
      agentRuntime: 'ai-sdk' as const,
      controlPlaneProvider: 'local' as const,
    }
    expect(() => validateConfig(config)).toThrow(/ai-sdk.*placement=server/)
  })
})
