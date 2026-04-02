import { describe, expect, it, beforeEach, vi, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'

// Mock appConfig before importing the hook
vi.mock('../../../shared/config/appConfig', () => ({
  getConfig: vi.fn(() => null),
}))

import { useChatCenteredShell } from '../useChatCenteredShell'
import { getConfig } from '../../../shared/config/appConfig'

describe('useChatCenteredShell', () => {
  let originalLocation

  beforeEach(() => {
    vi.mocked(getConfig).mockReturnValue(null)
    // Save original location and set up a writable search property
    originalLocation = window.location
    delete window.location
    window.location = { ...originalLocation, search: '' }
  })

  afterEach(() => {
    window.location = originalLocation
  })

  it('returns { enabled: false } when features.chatCenteredShell is false', () => {
    vi.mocked(getConfig).mockReturnValue({
      features: { chatCenteredShell: false },
    })

    const { result } = renderHook(() => useChatCenteredShell())
    expect(result.current.enabled).toBe(false)
  })

  it('returns { enabled: true } when features.chatCenteredShell is true', () => {
    vi.mocked(getConfig).mockReturnValue({
      features: { chatCenteredShell: true },
    })

    const { result } = renderHook(() => useChatCenteredShell())
    expect(result.current.enabled).toBe(true)
  })

  it('?layout=chat overrides flag to true', () => {
    vi.mocked(getConfig).mockReturnValue({ features: { chatCenteredShell: false } })
    window.location.search = '?layout=chat'
    const { result } = renderHook(() => useChatCenteredShell())
    expect(result.current.enabled).toBe(true)
    expect(result.current.layout).toBe('chat')
  })

  it('?layout=ide overrides flag to false', () => {
    vi.mocked(getConfig).mockReturnValue({ features: { chatCenteredShell: true } })
    window.location.search = '?layout=ide'
    const { result } = renderHook(() => useChatCenteredShell())
    expect(result.current.enabled).toBe(false)
    expect(result.current.layout).toBe('ide')
  })

  it('backward compat: ?shell=chat-centered still works', () => {
    vi.mocked(getConfig).mockReturnValue({ features: { chatCenteredShell: false } })
    window.location.search = '?shell=chat-centered'
    const { result } = renderHook(() => useChatCenteredShell())
    expect(result.current.enabled).toBe(true)
  })

  it('backward compat: ?shell=legacy still works', () => {
    vi.mocked(getConfig).mockReturnValue({ features: { chatCenteredShell: true } })
    window.location.search = '?shell=legacy'
    const { result } = renderHook(() => useChatCenteredShell())
    expect(result.current.enabled).toBe(false)
  })

  it('returns { enabled: false, layout: "ide" } when config is null', () => {
    vi.mocked(getConfig).mockReturnValue(null)
    const { result } = renderHook(() => useChatCenteredShell())
    expect(result.current.enabled).toBe(false)
    expect(result.current.layout).toBe('ide')
  })

  it('returns layout "ide" when features object is missing', () => {
    vi.mocked(getConfig).mockReturnValue({})
    const { result } = renderHook(() => useChatCenteredShell())
    expect(result.current.enabled).toBe(false)
    expect(result.current.layout).toBe('ide')
  })

  it('?layout takes precedence over config', () => {
    vi.mocked(getConfig).mockReturnValue({ features: { chatCenteredShell: true } })
    window.location.search = '?layout=ide'
    const { result: r1 } = renderHook(() => useChatCenteredShell())
    expect(r1.current.enabled).toBe(false)

    vi.mocked(getConfig).mockReturnValue({ features: { chatCenteredShell: false } })
    window.location.search = '?layout=chat'
    const { result: r2 } = renderHook(() => useChatCenteredShell())
    expect(r2.current.enabled).toBe(true)
  })
})
