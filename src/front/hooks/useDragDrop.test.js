/**
 * Tests for useDragDrop hook.
 */
import { describe, it, expect, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useDragDrop } from './useDragDrop'

function createOptions(overrides = {}) {
  return {
    openFileAtPosition: vi.fn(),
    centerGroupRef: { current: { id: 'center' } },
    ...overrides,
  }
}

describe('useDragDrop', () => {
  describe('showDndOverlay', () => {
    it('returns true for kurt-file drag type', () => {
      const { result } = renderHook(() => useDragDrop(createOptions()))

      const overlay = result.current.showDndOverlay({
        dataTransfer: { types: ['application/x-kurt-file'] },
      })

      expect(overlay).toBe(true)
    })

    it('returns false for other drag types', () => {
      const { result } = renderHook(() => useDragDrop(createOptions()))

      const overlay = result.current.showDndOverlay({
        dataTransfer: { types: ['text/plain'] },
      })

      expect(overlay).toBe(false)
    })
  })

  describe('onDidDrop', () => {
    it('opens file at group position when dropped on a group', () => {
      const opts = createOptions()
      const { result } = renderHook(() => useDragDrop(opts))

      const group = { id: 'target-group' }
      act(() => {
        result.current.onDidDrop({
          dataTransfer: { getData: () => JSON.stringify({ path: 'src/foo.js' }) },
          position: null,
          group,
        })
      })

      expect(opts.openFileAtPosition).toHaveBeenCalledWith(
        'src/foo.js',
        { referenceGroup: group },
      )
    })

    it('uses position when no group', () => {
      const opts = createOptions()
      const { result } = renderHook(() => useDragDrop(opts))

      const position = { direction: 'right', referencePanel: 'editor-bar' }
      act(() => {
        result.current.onDidDrop({
          dataTransfer: { getData: () => JSON.stringify({ path: 'src/foo.js' }) },
          position,
          group: null,
        })
      })

      expect(opts.openFileAtPosition).toHaveBeenCalledWith('src/foo.js', position)
    })

    it('falls back to centerGroupRef when no group or position', () => {
      const opts = createOptions()
      const { result } = renderHook(() => useDragDrop(opts))

      act(() => {
        result.current.onDidDrop({
          dataTransfer: { getData: () => JSON.stringify({ path: 'src/foo.js' }) },
          position: null,
          group: null,
        })
      })

      expect(opts.openFileAtPosition).toHaveBeenCalledWith(
        'src/foo.js',
        { referenceGroup: opts.centerGroupRef.current },
      )
    })

    it('falls back to filetree when no centerGroup', () => {
      const opts = createOptions({ centerGroupRef: { current: null } })
      const { result } = renderHook(() => useDragDrop(opts))

      act(() => {
        result.current.onDidDrop({
          dataTransfer: { getData: () => JSON.stringify({ path: 'src/foo.js' }) },
          position: null,
          group: null,
        })
      })

      expect(opts.openFileAtPosition).toHaveBeenCalledWith(
        'src/foo.js',
        { direction: 'right', referencePanel: 'filetree' },
      )
    })

    it('ignores events without kurt-file data', () => {
      const opts = createOptions()
      const { result } = renderHook(() => useDragDrop(opts))

      act(() => {
        result.current.onDidDrop({
          dataTransfer: { getData: () => '' },
          position: null,
          group: null,
        })
      })

      expect(opts.openFileAtPosition).not.toHaveBeenCalled()
    })

    it('ignores invalid JSON gracefully', () => {
      const opts = createOptions()
      const { result } = renderHook(() => useDragDrop(opts))

      act(() => {
        result.current.onDidDrop({
          dataTransfer: { getData: () => 'not-json' },
          position: null,
          group: null,
        })
      })

      expect(opts.openFileAtPosition).not.toHaveBeenCalled()
    })
  })
})
