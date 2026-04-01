import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { resetArtifactStore } from '../hooks/useArtifactController'

// We import the real modules (no mocks) so we test the full integration
import { useArtifactRouting } from '../hooks/useArtifactRouting'

describe('useArtifactRouting', () => {
  beforeEach(() => {
    resetArtifactStore()
  })

  it('handleOpenFile creates a code artifact and opens it', () => {
    const { result } = renderHook(() => useArtifactRouting('session-1'))

    act(() => {
      result.current.handleOpenFile('src/app.js')
    })

    expect(result.current.orderedIds).toHaveLength(1)
    const art = result.current.artifacts.get(result.current.orderedIds[0])
    expect(art.kind).toBe('code')
    expect(art.canonicalKey).toBe('src/app.js')
    expect(art.sourceSessionId).toBe('session-1')
  })

  it('handleOpenFile deduplicates by canonicalKey', () => {
    const { result } = renderHook(() => useArtifactRouting('session-1'))

    act(() => {
      result.current.handleOpenFile('src/app.js')
    })
    act(() => {
      result.current.handleOpenFile('src/app.js')
    })

    // Same canonical key -> only one artifact
    expect(result.current.orderedIds).toHaveLength(1)
  })

  it('handleToolResult routes write_file to an artifact', () => {
    const { result } = renderHook(() => useArtifactRouting('session-2'))

    act(() => {
      result.current.handleToolResult('write_file', { path: 'src/new.ts' }, { success: true })
    })

    expect(result.current.orderedIds).toHaveLength(1)
    const art = result.current.artifacts.get(result.current.orderedIds[0])
    expect(art.kind).toBe('code')
    expect(art.canonicalKey).toBe('src/new.ts')
  })

  it('handleToolResult routes read_file to an openable code artifact', () => {
    const { result } = renderHook(() => useArtifactRouting('session-2'))

    act(() => {
      const response = result.current.handleToolResult('read_file', { path: 'src/foo.js' }, { content: '...' })
      expect(response.shouldOpen).toBe(true)
      expect(response.artifact).toEqual(expect.objectContaining({
        kind: 'code',
        canonicalKey: 'src/foo.js',
      }))
    })

    expect(result.current.orderedIds).toHaveLength(1)
  })

  it('handleOpenPanel creates artifact from panel payload', () => {
    const { result } = renderHook(() => useArtifactRouting('session-3'))

    act(() => {
      result.current.handleOpenPanel({
        type: 'review',
        params: { path: 'src/auth.js' },
        title: 'Auth Review',
      })
    })

    expect(result.current.orderedIds).toHaveLength(1)
    const art = result.current.artifacts.get(result.current.orderedIds[0])
    expect(art.kind).toBe('review')
    expect(art.title).toBe('Auth Review')
  })

  it('handleArtifactCardOpen creates artifact from card data', () => {
    const { result } = renderHook(() => useArtifactRouting('session-4', 'msg-10'))

    act(() => {
      result.current.handleArtifactCardOpen({
        title: 'Revenue Chart',
        kind: 'chart',
        id: 'chart-revenue',
      })
    })

    expect(result.current.orderedIds).toHaveLength(1)
    const art = result.current.artifacts.get(result.current.orderedIds[0])
    expect(art.kind).toBe('chart')
    expect(art.title).toBe('Revenue Chart')
    expect(art.sourceSessionId).toBe('session-4')
    expect(art.sourceMessageId).toBe('msg-10')
  })

  it('all entry points converge: same canonicalKey deduplicates across routes', () => {
    const { result } = renderHook(() => useArtifactRouting('session-5'))

    // Open via file
    act(() => {
      result.current.handleOpenFile('src/shared.js')
    })
    // Open same path via tool result
    act(() => {
      result.current.handleToolResult('write_file', { path: 'src/shared.js' }, {})
    })

    // Should still be one artifact
    expect(result.current.orderedIds).toHaveLength(1)
  })

  it('handleOpenFile rejects empty and null paths', () => {
    const { result } = renderHook(() => useArtifactRouting('session-6'))

    act(() => {
      result.current.handleOpenFile('')
      result.current.handleOpenFile(null)
      result.current.handleOpenFile(undefined)
      result.current.handleOpenFile('   ')
    })

    expect(result.current.orderedIds).toHaveLength(0)
  })
})
