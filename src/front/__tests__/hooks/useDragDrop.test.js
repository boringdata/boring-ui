import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useDragDrop } from '../../hooks/useDragDrop'

describe('useDragDrop', () => {
  let openFileAtPosition
  let centerGroupRef

  beforeEach(() => {
    vi.clearAllMocks()
    openFileAtPosition = vi.fn()
    centerGroupRef = { current: null }
  })

  function render(overrides = {}) {
    return renderHook(() =>
      useDragDrop({
        openFileAtPosition,
        centerGroupRef,
        ...overrides,
      }),
    )
  }

  describe('showDndOverlay', () => {
    it('returns true for kurt-file drag type', () => {
      const { result } = render()
      const event = {
        dataTransfer: { types: ['application/x-kurt-file'] },
      }
      expect(result.current.showDndOverlay(event)).toBe(true)
    })

    it('returns false for other drag types', () => {
      const { result } = render()
      const event = {
        dataTransfer: { types: ['text/plain'] },
      }
      expect(result.current.showDndOverlay(event)).toBe(false)
    })

    it('returns false for empty types', () => {
      const { result } = render()
      const event = {
        dataTransfer: { types: [] },
      }
      expect(result.current.showDndOverlay(event)).toBe(false)
    })
  })

  describe('onDidDrop', () => {
    it('opens file at group position when dropped on group', () => {
      const { result } = render()
      const group = { id: 'center' }

      act(() => {
        result.current.onDidDrop({
          dataTransfer: {
            getData: () => JSON.stringify({ path: 'src/app.js' }),
          },
          group,
          position: null,
        })
      })

      expect(openFileAtPosition).toHaveBeenCalledWith('src/app.js', {
        referenceGroup: group,
      })
    })

    it('opens file at position when dropped at split', () => {
      const { result } = render()
      const position = { direction: 'right', referencePanel: 'editor-foo' }

      act(() => {
        result.current.onDidDrop({
          dataTransfer: {
            getData: () => JSON.stringify({ path: 'src/b.js' }),
          },
          group: null,
          position,
        })
      })

      expect(openFileAtPosition).toHaveBeenCalledWith('src/b.js', position)
    })

    it('falls back to center group', () => {
      const centerGroup = { id: 'center-group' }
      centerGroupRef.current = centerGroup
      const { result } = render()

      act(() => {
        result.current.onDidDrop({
          dataTransfer: {
            getData: () => JSON.stringify({ path: 'src/c.js' }),
          },
          group: null,
          position: null,
        })
      })

      expect(openFileAtPosition).toHaveBeenCalledWith('src/c.js', {
        referenceGroup: centerGroup,
      })
    })

    it('falls back to right of filetree when no center group', () => {
      const { result } = render()

      act(() => {
        result.current.onDidDrop({
          dataTransfer: {
            getData: () => JSON.stringify({ path: 'src/d.js' }),
          },
          group: null,
          position: null,
        })
      })

      expect(openFileAtPosition).toHaveBeenCalledWith('src/d.js', {
        direction: 'right',
        referencePanel: 'filetree',
      })
    })

    it('ignores drop with no file data', () => {
      const { result } = render()

      act(() => {
        result.current.onDidDrop({
          dataTransfer: { getData: () => '' },
          group: null,
          position: null,
        })
      })

      expect(openFileAtPosition).not.toHaveBeenCalled()
    })

    it('ignores invalid JSON', () => {
      const { result } = render()

      act(() => {
        result.current.onDidDrop({
          dataTransfer: { getData: () => 'not-json' },
          group: null,
          position: null,
        })
      })

      expect(openFileAtPosition).not.toHaveBeenCalled()
    })
  })
})
