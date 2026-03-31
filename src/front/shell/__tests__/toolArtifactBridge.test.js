import { describe, expect, it } from 'vitest'
import {
  bridgeToolResultToArtifact,
  bridgeOpenPanelToArtifact,
  bridgeArtifactCardToArtifact,
} from '../toolArtifactBridge'

describe('toolArtifactBridge', () => {
  const activeSessionId = 'session-123'

  it('write_file with path returns shouldOpen true + code artifact', () => {
    const result = bridgeToolResultToArtifact(
      'write_file',
      { path: 'src/auth.js', content: 'export function auth() {}' },
      { success: true },
      activeSessionId
    )

    expect(result.shouldOpen).toBe(true)
    expect(result.artifact).not.toBeNull()
    expect(result.artifact.kind).toBe('code')
    expect(result.artifact.canonicalKey).toBe('src/auth.js')
    expect(result.artifact.title).toBe('auth.js')
    expect(result.artifact.source).toBe('tool')
    expect(result.artifact.sourceSessionId).toBe(activeSessionId)
  })

  it('edit_file with path returns shouldOpen true + code artifact', () => {
    const result = bridgeToolResultToArtifact(
      'edit_file',
      { path: 'src/utils.ts', old_string: 'foo', new_string: 'bar' },
      { success: true },
      activeSessionId
    )

    expect(result.shouldOpen).toBe(true)
    expect(result.artifact).not.toBeNull()
    expect(result.artifact.kind).toBe('code')
    expect(result.artifact.canonicalKey).toBe('src/utils.ts')
  })

  it('read_file returns shouldOpen false', () => {
    const result = bridgeToolResultToArtifact(
      'read_file',
      { path: 'src/auth.js' },
      { content: 'file contents' },
      activeSessionId
    )

    expect(result.shouldOpen).toBe(false)
    expect(result.artifact).toBeNull()
  })

  it('bash returns shouldOpen false', () => {
    const result = bridgeToolResultToArtifact(
      'bash',
      { command: 'ls -la' },
      { stdout: 'total 0', exitCode: 0 },
      activeSessionId
    )

    expect(result.shouldOpen).toBe(false)
    expect(result.artifact).toBeNull()
  })

  it('search_files returns shouldOpen false', () => {
    const result = bridgeToolResultToArtifact(
      'search_files',
      { pattern: 'auth', path: 'src/' },
      { matches: [] },
      activeSessionId
    )

    expect(result.shouldOpen).toBe(false)
    expect(result.artifact).toBeNull()
  })

  it('open_file returns shouldOpen true + code artifact', () => {
    const result = bridgeToolResultToArtifact(
      'open_file',
      { path: 'src/index.jsx' },
      { success: true },
      activeSessionId
    )

    expect(result.shouldOpen).toBe(true)
    expect(result.artifact).not.toBeNull()
    expect(result.artifact.kind).toBe('code')
    expect(result.artifact.canonicalKey).toBe('src/index.jsx')
    expect(result.artifact.title).toBe('index.jsx')
  })

  it('unknown tool returns shouldOpen false', () => {
    const result = bridgeToolResultToArtifact(
      'some_custom_tool',
      { foo: 'bar' },
      { result: 'ok' },
      activeSessionId
    )

    expect(result.shouldOpen).toBe(false)
    expect(result.artifact).toBeNull()
  })

  it('same canonicalKey produces same canonicalKey in artifact (dedup-ready)', () => {
    const result1 = bridgeToolResultToArtifact(
      'write_file',
      { path: 'src/auth.js', content: 'v1' },
      { success: true },
      activeSessionId
    )

    const result2 = bridgeToolResultToArtifact(
      'edit_file',
      { path: 'src/auth.js', old_string: 'v1', new_string: 'v2' },
      { success: true },
      activeSessionId
    )

    expect(result1.artifact.canonicalKey).toBe('src/auth.js')
    expect(result2.artifact.canonicalKey).toBe('src/auth.js')
    // Same canonical key allows the artifact controller to dedup
    expect(result1.artifact.canonicalKey).toBe(result2.artifact.canonicalKey)
    // But IDs should be different (each bridge call generates a unique ID)
    expect(result1.artifact.id).not.toBe(result2.artifact.id)
  })

  // --- Phase 5: Extended artifact types ---

  it('open_review creates a review artifact', () => {
    const result = bridgeToolResultToArtifact(
      'open_review',
      { path: 'src/auth.js' },
      {},
      activeSessionId
    )

    expect(result.shouldOpen).toBe(true)
    expect(result.artifact.kind).toBe('review')
    expect(result.artifact.canonicalKey).toBe('review:src/auth.js')
    expect(result.artifact.title).toBe('auth.js')
  })

  it('open_chart creates a chart artifact', () => {
    const result = bridgeToolResultToArtifact(
      'open_chart',
      { id: 'revenue-q1', title: 'Revenue Q1' },
      {},
      activeSessionId
    )

    expect(result.shouldOpen).toBe(true)
    expect(result.artifact.kind).toBe('chart')
    expect(result.artifact.canonicalKey).toBe('chart:revenue-q1')
    expect(result.artifact.title).toBe('Revenue Q1')
  })

  it('open_table creates a table artifact', () => {
    const result = bridgeToolResultToArtifact(
      'open_table',
      { id: 'users-list', title: 'Users' },
      {},
      activeSessionId
    )

    expect(result.shouldOpen).toBe(true)
    expect(result.artifact.kind).toBe('table')
    expect(result.artifact.canonicalKey).toBe('table:users-list')
    expect(result.artifact.title).toBe('Users')
  })

  it('includes provenance messageId when provided', () => {
    const result = bridgeToolResultToArtifact(
      'open_file',
      { path: 'src/main.js' },
      {},
      activeSessionId,
      'msg-42'
    )

    expect(result.artifact.sourceSessionId).toBe(activeSessionId)
    expect(result.artifact.sourceMessageId).toBe('msg-42')
  })

  it('messageId defaults to null when not provided', () => {
    const result = bridgeToolResultToArtifact(
      'open_file',
      { path: 'src/main.js' },
      {},
      activeSessionId
    )

    expect(result.artifact.sourceMessageId).toBeNull()
  })
})

describe('bridgeOpenPanelToArtifact', () => {
  const activeSessionId = 'session-456'

  it('creates artifact from open_panel payload', () => {
    const result = bridgeOpenPanelToArtifact(
      { type: 'review', params: { path: 'src/api.js' }, title: 'API Review' },
      activeSessionId
    )

    expect(result.shouldOpen).toBe(true)
    expect(result.artifact.kind).toBe('review')
    expect(result.artifact.canonicalKey).toBe('src/api.js')
    expect(result.artifact.title).toBe('API Review')
    expect(result.artifact.sourceSessionId).toBe(activeSessionId)
  })

  it('uses component as fallback for type', () => {
    const result = bridgeOpenPanelToArtifact(
      { component: 'chart-canvas', params: {} },
      activeSessionId
    )

    expect(result.artifact.kind).toBe('chart-canvas')
  })

  it('returns shouldOpen false for null payload', () => {
    const result = bridgeOpenPanelToArtifact(null, activeSessionId)
    expect(result.shouldOpen).toBe(false)
  })

  it('includes messageId provenance', () => {
    const result = bridgeOpenPanelToArtifact(
      { type: 'code', params: { path: 'x.js' } },
      activeSessionId,
      'msg-99'
    )

    expect(result.artifact.sourceMessageId).toBe('msg-99')
  })
})

describe('bridgeArtifactCardToArtifact', () => {
  it('creates artifact from ArtifactCard data', () => {
    const cardData = {
      title: 'Revenue Chart',
      kind: 'chart',
      id: 'card-rev',
    }

    const artifact = bridgeArtifactCardToArtifact(cardData, 'session-1', 'msg-1')

    expect(artifact).not.toBeNull()
    expect(artifact.kind).toBe('chart')
    expect(artifact.title).toBe('Revenue Chart')
    expect(artifact.canonicalKey).toBe('card-rev')
    expect(artifact.sourceSessionId).toBe('session-1')
    expect(artifact.sourceMessageId).toBe('msg-1')
  })

  it('defaults kind to document when not specified', () => {
    const artifact = bridgeArtifactCardToArtifact({ title: 'Notes' }, 'session-1')
    expect(artifact.kind).toBe('document')
  })

  it('returns null for null input', () => {
    const artifact = bridgeArtifactCardToArtifact(null, 'session-1')
    expect(artifact).toBeNull()
  })

  it('uses canonicalKey from card data when available', () => {
    const artifact = bridgeArtifactCardToArtifact(
      { title: 'Test', kind: 'code', canonicalKey: 'custom:key' },
      'session-1'
    )
    expect(artifact.canonicalKey).toBe('custom:key')
  })
})
