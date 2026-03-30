import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useFileStorage } from '../useFileStorage'

describe('useFileStorage', () => {
  let urlCounter = 0
  let createMock
  let revokeMock

  beforeEach(() => {
    urlCounter = 0
    createMock = vi.fn(() => `blob:test-${++urlCounter}`)
    revokeMock = vi.fn()
    // Assign mocks directly. vitest's afterEach calls vi.clearAllMocks
    // but does NOT restore these -- which is what we want so the hook's
    // cleanup effect can still call revokeObjectURL after the test body.
    URL.createObjectURL = createMock
    URL.revokeObjectURL = revokeMock
  })

  it('storeFile returns a reference object with id, name, size, type', () => {
    const { result } = renderHook(() => useFileStorage())
    const file = new File(['hello'], 'test.txt', { type: 'text/plain' })

    let ref
    act(() => {
      ref = result.current.storeFile(file)
    })

    expect(ref).toMatchObject({
      id: expect.any(String),
      name: 'test.txt',
      size: 5,
      type: 'text/plain',
    })
  })

  it('getFileUrl returns a blob URL for a stored file', () => {
    const { result } = renderHook(() => useFileStorage())
    const file = new File(['data'], 'doc.pdf', { type: 'application/pdf' })

    let ref
    act(() => {
      ref = result.current.storeFile(file)
    })

    const url = result.current.getFileUrl(ref.id)
    expect(url).toMatch(/^blob:/)
  })

  it('releaseFile revokes the blob URL', () => {
    const { result } = renderHook(() => useFileStorage())
    const file = new File(['data'], 'img.png', { type: 'image/png' })

    let ref
    act(() => {
      ref = result.current.storeFile(file)
    })

    const url = result.current.getFileUrl(ref.id)

    act(() => {
      result.current.releaseFile(ref.id)
    })

    expect(revokeMock).toHaveBeenCalledWith(url)
    // After release, getFileUrl returns null
    expect(result.current.getFileUrl(ref.id)).toBeNull()
  })

  it('releaseAll revokes all blob URLs', () => {
    const { result } = renderHook(() => useFileStorage())
    const file1 = new File(['a'], 'a.txt', { type: 'text/plain' })
    const file2 = new File(['b'], 'b.txt', { type: 'text/plain' })

    act(() => {
      result.current.storeFile(file1)
      result.current.storeFile(file2)
    })

    act(() => {
      result.current.releaseAll()
    })

    expect(revokeMock).toHaveBeenCalledTimes(2)
  })

  it('does NOT use IndexedDB for file storage', () => {
    // Reset the indexedDB.open mock counter
    const openSpy = vi.spyOn(globalThis.indexedDB, 'open')
    openSpy.mockClear()

    const { result } = renderHook(() => useFileStorage())
    const file = new File(['data'], 'test.txt', { type: 'text/plain' })

    act(() => {
      result.current.storeFile(file)
    })

    expect(openSpy).not.toHaveBeenCalled()
    openSpy.mockRestore()
  })

  it('on unmount, revokes all blob URLs', () => {
    const { result, unmount } = renderHook(() => useFileStorage())
    const file = new File(['data'], 'test.txt', { type: 'text/plain' })

    act(() => {
      result.current.storeFile(file)
    })

    unmount()

    expect(revokeMock).toHaveBeenCalled()
  })
})
