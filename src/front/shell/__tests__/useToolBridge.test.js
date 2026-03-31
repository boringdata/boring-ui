import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useToolBridge, SURFACE_OPEN_FILE_BRIDGE, SURFACE_OPEN_PANEL_BRIDGE } from '../useToolBridge'

describe('useToolBridge', () => {
  let openArtifact

  beforeEach(() => {
    openArtifact = vi.fn()
    // Clean up any leftover bridge functions
    delete window[SURFACE_OPEN_FILE_BRIDGE]
    delete window[SURFACE_OPEN_PANEL_BRIDGE]
  })

  afterEach(() => {
    delete window[SURFACE_OPEN_FILE_BRIDGE]
    delete window[SURFACE_OPEN_PANEL_BRIDGE]
  })

  it('sets window.__SURFACE_OPEN_FILE__ on mount', () => {
    renderHook(() => useToolBridge({ openArtifact }))
    expect(typeof window[SURFACE_OPEN_FILE_BRIDGE]).toBe('function')
  })

  it('sets window.__SURFACE_OPEN_PANEL__ on mount', () => {
    renderHook(() => useToolBridge({ openArtifact }))
    expect(typeof window[SURFACE_OPEN_PANEL_BRIDGE]).toBe('function')
  })

  it('calling __SURFACE_OPEN_FILE__ triggers openArtifact with a code artifact', () => {
    renderHook(() => useToolBridge({ openArtifact, activeSessionId: 'session-1' }))

    act(() => {
      window[SURFACE_OPEN_FILE_BRIDGE]('src/hello.js')
    })

    expect(openArtifact).toHaveBeenCalledTimes(1)
    const artifact = openArtifact.mock.calls[0][0]
    expect(artifact).toMatchObject({
      canonicalKey: 'src/hello.js',
      kind: 'code',
      title: 'hello.js',
      source: 'tool',
      sourceSessionId: 'session-1',
    })
    expect(artifact.id).toMatch(/^art-/)
  })

  it('calling __SURFACE_OPEN_PANEL__ triggers openArtifact with the panel artifact', () => {
    renderHook(() => useToolBridge({ openArtifact, activeSessionId: 'session-2' }))

    act(() => {
      window[SURFACE_OPEN_PANEL_BRIDGE]({
        type: 'review',
        params: { path: 'src/review.js', title: 'Code Review' },
      })
    })

    expect(openArtifact).toHaveBeenCalledTimes(1)
    const artifact = openArtifact.mock.calls[0][0]
    expect(artifact).toMatchObject({
      canonicalKey: 'src/review.js',
      kind: 'review',
      title: 'Code Review',
      source: 'tool',
      sourceSessionId: 'session-2',
    })
  })

  it('does nothing for empty path in __SURFACE_OPEN_FILE__', () => {
    renderHook(() => useToolBridge({ openArtifact }))

    act(() => {
      window[SURFACE_OPEN_FILE_BRIDGE]('')
    })

    expect(openArtifact).not.toHaveBeenCalled()
  })

  it('does nothing for null/undefined path in __SURFACE_OPEN_FILE__', () => {
    renderHook(() => useToolBridge({ openArtifact }))

    act(() => {
      window[SURFACE_OPEN_FILE_BRIDGE](null)
      window[SURFACE_OPEN_FILE_BRIDGE](undefined)
    })

    expect(openArtifact).not.toHaveBeenCalled()
  })

  it('cleans up bridge functions on unmount', () => {
    const { unmount } = renderHook(() => useToolBridge({ openArtifact }))

    expect(typeof window[SURFACE_OPEN_FILE_BRIDGE]).toBe('function')
    expect(typeof window[SURFACE_OPEN_PANEL_BRIDGE]).toBe('function')

    unmount()

    expect(window[SURFACE_OPEN_FILE_BRIDGE]).toBeUndefined()
    expect(window[SURFACE_OPEN_PANEL_BRIDGE]).toBeUndefined()
  })

  it('uses updated openArtifact ref without re-registering bridge', () => {
    const openArtifact2 = vi.fn()

    const { rerender } = renderHook(
      ({ openArtifact: oa }) => useToolBridge({ openArtifact: oa }),
      { initialProps: { openArtifact } },
    )

    // The bridge function identity should be set once
    const bridgeFn = window[SURFACE_OPEN_FILE_BRIDGE]

    rerender({ openArtifact: openArtifact2 })

    // Same function identity (not re-registered)
    expect(window[SURFACE_OPEN_FILE_BRIDGE]).toBe(bridgeFn)

    // But calling it should use the new openArtifact
    act(() => {
      window[SURFACE_OPEN_FILE_BRIDGE]('src/test.js')
    })

    expect(openArtifact).not.toHaveBeenCalled()
    expect(openArtifact2).toHaveBeenCalledTimes(1)
  })
})
