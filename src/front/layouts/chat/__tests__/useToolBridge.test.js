import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import {
  PI_LIST_TABS_BRIDGE,
  PI_OPEN_FILE_BRIDGE,
  PI_OPEN_PANEL_BRIDGE,
} from '../../../shared/providers/pi/uiBridge'
import { useToolBridge, SURFACE_OPEN_FILE_BRIDGE, SURFACE_OPEN_PANEL_BRIDGE } from '../hooks/useToolBridge'

describe('useToolBridge', () => {
  let openArtifact

  beforeEach(() => {
    openArtifact = vi.fn()
    // Clean up any leftover bridge functions
    delete window[SURFACE_OPEN_FILE_BRIDGE]
    delete window[SURFACE_OPEN_PANEL_BRIDGE]
    delete window[PI_OPEN_FILE_BRIDGE]
    delete window[PI_OPEN_PANEL_BRIDGE]
    delete window[PI_LIST_TABS_BRIDGE]
  })

  afterEach(() => {
    delete window[SURFACE_OPEN_FILE_BRIDGE]
    delete window[SURFACE_OPEN_PANEL_BRIDGE]
    delete window[PI_OPEN_FILE_BRIDGE]
    delete window[PI_OPEN_PANEL_BRIDGE]
    delete window[PI_LIST_TABS_BRIDGE]
  })

  it('sets window.__SURFACE_OPEN_FILE__ on mount', () => {
    renderHook(() => useToolBridge({ openArtifact }))
    expect(typeof window[SURFACE_OPEN_FILE_BRIDGE]).toBe('function')
  })

  it('sets window.__SURFACE_OPEN_PANEL__ on mount', () => {
    renderHook(() => useToolBridge({ openArtifact }))
    expect(typeof window[SURFACE_OPEN_PANEL_BRIDGE]).toBe('function')
  })

  it('registers legacy PI bridge aliases on mount', () => {
    renderHook(() => useToolBridge({ openArtifact }))
    expect(typeof window[PI_OPEN_FILE_BRIDGE]).toBe('function')
    expect(typeof window[PI_OPEN_PANEL_BRIDGE]).toBe('function')
    expect(typeof window[PI_LIST_TABS_BRIDGE]).toBe('function')
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

  it('legacy __BORING_UI_PI_OPEN_FILE__ opens the same code artifact path', () => {
    renderHook(() => useToolBridge({ openArtifact, activeSessionId: 'session-legacy' }))

    act(() => {
      window[PI_OPEN_FILE_BRIDGE]('README.md')
    })

    expect(openArtifact).toHaveBeenCalledWith(expect.objectContaining({
      canonicalKey: 'README.md',
      kind: 'code',
      sourceSessionId: 'session-legacy',
    }))
  })

  it('legacy __BORING_UI_PI_LIST_TABS__ reports open code artifacts', () => {
    const artifacts = new Map([
      ['art-1', { id: 'art-1', kind: 'code', canonicalKey: 'README.md', params: { path: 'README.md' } }],
      ['art-2', { id: 'art-2', kind: 'chart', canonicalKey: 'chart:usage' }],
      ['art-3', { id: 'art-3', kind: 'code', canonicalKey: 'src/app.js', params: { path: 'src/app.js' } }],
    ])

    renderHook(() => useToolBridge({
      openArtifact,
      artifacts,
      activeArtifactId: 'art-3',
    }))

    expect(window[PI_LIST_TABS_BRIDGE]()).toEqual({
      tabs: ['README.md', 'src/app.js'],
      activeFile: 'src/app.js',
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
    expect(typeof window[PI_OPEN_FILE_BRIDGE]).toBe('function')
    expect(typeof window[PI_OPEN_PANEL_BRIDGE]).toBe('function')
    expect(typeof window[PI_LIST_TABS_BRIDGE]).toBe('function')

    unmount()

    expect(window[SURFACE_OPEN_FILE_BRIDGE]).toBeUndefined()
    expect(window[SURFACE_OPEN_PANEL_BRIDGE]).toBeUndefined()
    expect(window[PI_OPEN_FILE_BRIDGE]).toBeUndefined()
    expect(window[PI_OPEN_PANEL_BRIDGE]).toBeUndefined()
    expect(window[PI_LIST_TABS_BRIDGE]).toBeUndefined()
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
