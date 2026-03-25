import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { mkdirSync, rmSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import {
  resolveWorkspaceBackend,
  resolveWorkspacePath,
  resolvePathBeneath,
  isSingleModeForced,
} from '../workspace/resolver.js'
import { loadConfig } from '../config.js'

const TEST_ROOT = join(tmpdir(), `resolver-test-${Date.now()}`)

beforeAll(() => {
  mkdirSync(TEST_ROOT, { recursive: true })
})

afterAll(() => {
  rmSync(TEST_ROOT, { recursive: true, force: true })
})

describe('resolveWorkspaceBackend', () => {
  it('resolves bwrap backend and creates workspace dir', () => {
    const config = {
      ...loadConfig(),
      workspaceRoot: TEST_ROOT,
      workspaceBackend: 'bwrap' as const,
    }
    const result = resolveWorkspaceBackend(config, 'ws-123')
    expect(result.backend).toBe('bwrap')
    expect(result.capabilities).toContain('workspace.files')
    expect(result.capabilities).toContain('workspace.exec')
    expect(result.capabilities).toContain('workspace.git')
    expect(existsSync(result.workspacePath)).toBe(true)
  })

  it('throws for lightningfs (browser-only)', () => {
    const config = {
      ...loadConfig(),
      workspaceRoot: TEST_ROOT,
      workspaceBackend: 'lightningfs' as const,
    }
    expect(() => resolveWorkspaceBackend(config, 'ws-123')).toThrow(
      /browser.*not.*server/i,
    )
  })

  it('throws for justbash (browser-only)', () => {
    const config = {
      ...loadConfig(),
      workspaceRoot: TEST_ROOT,
      workspaceBackend: 'justbash' as const,
    }
    expect(() => resolveWorkspaceBackend(config, 'ws-123')).toThrow(
      /browser.*not.*server/i,
    )
  })
})

describe('resolveWorkspacePath', () => {
  it('joins root + id', () => {
    const result = resolveWorkspacePath(TEST_ROOT, 'ws-abc')
    expect(result).toBe(join(TEST_ROOT, 'ws-abc'))
  })

  it('rejects path traversal', () => {
    expect(() => resolveWorkspacePath(TEST_ROOT, '../escape')).toThrow(
      /path traversal/i,
    )
  })

  it('rejects absolute path escape', () => {
    expect(() => resolveWorkspacePath(TEST_ROOT, '/etc/passwd')).toThrow(
      /path traversal/i,
    )
  })
})

describe('resolvePathBeneath', () => {
  it('resolves relative path within workspace', () => {
    const result = resolvePathBeneath(TEST_ROOT, 'subdir/file.txt')
    expect(result).toBe(join(TEST_ROOT, 'subdir/file.txt'))
  })

  it('rejects path traversal', () => {
    expect(() => resolvePathBeneath(TEST_ROOT, '../../etc/passwd')).toThrow(
      /path traversal/i,
    )
  })
})

describe('isSingleModeForced', () => {
  it('returns true when header is present', () => {
    expect(isSingleModeForced({ 'x-boring-local-workspace': 'true' })).toBe(true)
  })

  it('returns false when header is absent', () => {
    expect(isSingleModeForced({})).toBe(false)
  })

  it('handles array header values', () => {
    expect(isSingleModeForced({ 'x-boring-local-workspace': ['yes'] })).toBe(true)
    expect(isSingleModeForced({ 'x-boring-local-workspace': [] })).toBe(false)
  })
})
