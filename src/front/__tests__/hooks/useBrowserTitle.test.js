import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import {
  useBrowserTitle,
  computeTitle,
  getFolderName,
} from '../../hooks/useBrowserTitle'

describe('getFolderName', () => {
  it('extracts last segment from path', () => {
    expect(getFolderName('/home/user/project')).toBe('project')
  })

  it('handles trailing slash', () => {
    expect(getFolderName('/home/user/project/')).toBe('project')
  })

  it('returns null for null input', () => {
    expect(getFolderName(null)).toBeNull()
  })

  it('returns null for empty string', () => {
    expect(getFolderName('')).toBeNull()
  })

  it('handles single segment', () => {
    expect(getFolderName('/project')).toBe('project')
  })
})

describe('computeTitle', () => {
  it('uses titleFormat function when provided', () => {
    const config = {
      branding: {
        titleFormat: ({ folder }) => `Custom: ${folder}`,
        name: 'My App',
      },
    }
    expect(computeTitle(config, '/home/user/project')).toBe('Custom: project')
  })

  it('titleFormat receives folder and workspace', () => {
    const titleFormat = vi.fn(() => 'title')
    const config = { branding: { titleFormat } }
    computeTitle(config, '/home/user/myproject')

    expect(titleFormat).toHaveBeenCalledWith({
      folder: 'myproject',
      workspace: 'myproject',
    })
  })

  it('titleFormat with null projectRoot passes null folder', () => {
    const titleFormat = vi.fn(() => 'title')
    const config = { branding: { titleFormat } }
    computeTitle(config, null)

    expect(titleFormat).toHaveBeenCalledWith({
      folder: null,
      workspace: null,
    })
  })

  it('uses "folder - name" when titleFormat is not a function', () => {
    const config = { branding: { name: 'My App' } }
    expect(computeTitle(config, '/home/user/project')).toBe(
      'project - My App',
    )
  })

  it('uses app name only when no projectRoot', () => {
    const config = { branding: { name: 'My App' } }
    expect(computeTitle(config, null)).toBe('My App')
  })

  it('defaults to "Boring UI" when no branding name', () => {
    expect(computeTitle({}, null)).toBe('Boring UI')
  })

  it('defaults to "Boring UI" with null config', () => {
    expect(computeTitle(null, null)).toBe('Boring UI')
  })

  it('uses folder with default name when only projectRoot', () => {
    expect(computeTitle({}, '/home/user/myapp')).toBe('myapp - Boring UI')
  })
})

describe('useBrowserTitle', () => {
  let originalTitle

  beforeEach(() => {
    originalTitle = document.title
  })

  it('sets document.title from config', () => {
    const config = { branding: { name: 'Test App' } }
    renderHook(() => useBrowserTitle(config, null))
    expect(document.title).toBe('Test App')
  })

  it('sets document.title with folder and name', () => {
    const config = { branding: { name: 'IDE' } }
    renderHook(() => useBrowserTitle(config, '/home/user/project'))
    expect(document.title).toBe('project - IDE')
  })

  it('uses titleFormat function', () => {
    const config = {
      branding: {
        titleFormat: ({ folder }) => `[${folder}]`,
      },
    }
    renderHook(() => useBrowserTitle(config, '/home/user/myapp'))
    expect(document.title).toBe('[myapp]')
  })

  it('defaults to Boring UI', () => {
    renderHook(() => useBrowserTitle({}, null))
    expect(document.title).toBe('Boring UI')
  })

  it('updates title when projectRoot changes', () => {
    const config = { branding: { name: 'App' } }
    const { rerender } = renderHook(
      ({ root }) => useBrowserTitle(config, root),
      { initialProps: { root: null } },
    )
    expect(document.title).toBe('App')

    rerender({ root: '/home/user/project' })
    expect(document.title).toBe('project - App')
  })
})
