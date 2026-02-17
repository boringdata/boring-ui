import { describe, expect, it } from 'vitest'
import {
  extractUserEmail,
  extractWorkspaceId,
  extractWorkspaceSettingsPayload,
  getRuntimeStatus,
  getWorkspaceIdFromPathname,
  getWorkspacePathSuffix,
  isRuntimeReady,
  normalizeWorkspaceList,
  shouldRetryRuntime,
} from './controlPlane'

describe('controlPlane utils', () => {
  it('normalizes workspace list payloads from common response envelopes', () => {
    expect(
      normalizeWorkspaceList({
        workspaces: [
          { id: 'ws-1', name: 'One' },
          { workspace_id: 'ws-2', workspace_name: 'Two' },
          { id: 'ws-1', name: 'Duplicate' },
        ],
      }),
    ).toEqual([
      { id: 'ws-1', name: 'One' },
      { id: 'ws-2', name: 'Two' },
    ])

    expect(
      normalizeWorkspaceList({
        data: {
          items: [{ workspaceId: 'ws-3', workspaceName: 'Three' }],
        },
      }),
    ).toEqual([{ id: 'ws-3', name: 'Three' }])
  })

  it('extracts workspace id from direct and nested payloads', () => {
    expect(extractWorkspaceId({ id: 'ws-direct' })).toBe('ws-direct')
    expect(extractWorkspaceId({ workspace: { workspace_id: 'ws-nested' } })).toBe('ws-nested')
    expect(extractWorkspaceId({ data: { workspaceId: 'ws-data' } })).toBe('ws-data')
    expect(extractWorkspaceId({ workspaces: [{ id: 'ws-list' }] })).toBe('ws-list')
  })

  it('extracts user email from me payload variants', () => {
    expect(extractUserEmail({ email: 'direct@example.com' })).toBe('direct@example.com')
    expect(extractUserEmail({ user: { email: 'nested@example.com' } })).toBe('nested@example.com')
    expect(extractUserEmail({ data: { email: 'data@example.com' } })).toBe('data@example.com')
  })

  it('parses canonical workspace paths', () => {
    expect(getWorkspaceIdFromPathname('/w/ws-123/app')).toBe('ws-123')
    expect(getWorkspaceIdFromPathname('/w/ws%2Fencoded/setup')).toBe('ws/encoded')
    expect(getWorkspaceIdFromPathname('/api/v1/workspaces')).toBe('')
    expect(getWorkspacePathSuffix('/w/ws-123/app/editor')).toBe('app/editor')
    expect(getWorkspacePathSuffix('/w/ws-123/')).toBe('')
  })

  it('evaluates runtime status and retry conditions', () => {
    expect(getRuntimeStatus({ runtime: { state: 'READY' } })).toBe('ready')
    expect(isRuntimeReady({ runtime: { status: 'running' } })).toBe(true)
    expect(isRuntimeReady({ runtime: { status: 'error' } })).toBe(false)
    expect(shouldRetryRuntime({ runtime: { status: 'failed' } })).toBe(true)
    expect(shouldRetryRuntime({ retryable: true })).toBe(true)
    expect(shouldRetryRuntime({ status: 'provisioning' })).toBe(false)
  })

  it('extracts workspace settings payload for update calls', () => {
    expect(extractWorkspaceSettingsPayload({ settings: { region: 'us' } })).toEqual({ region: 'us' })
    expect(extractWorkspaceSettingsPayload({ workspace_settings: { shell: 'zsh' } })).toEqual({ shell: 'zsh' })
    expect(extractWorkspaceSettingsPayload({ data: { settings: { theme: 'dark' } } })).toEqual({
      theme: 'dark',
    })
    expect(extractWorkspaceSettingsPayload({ data: { editor: 'vim' } })).toEqual({ editor: 'vim' })
  })
})
