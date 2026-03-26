import { renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import useViewportBreakpoint from '../../hooks/useViewportBreakpoint'
import { simulateWindowResize } from '../utils/user-events'

describe('useViewportBreakpoint', () => {
  afterEach(() => {
    simulateWindowResize(1280, 800)
  })

  it('tracks whether the viewport is at or below the provided breakpoint', () => {
    simulateWindowResize(1280, 800)
    const { result } = renderHook(() => useViewportBreakpoint(960))

    expect(result.current).toBe(false)

    simulateWindowResize(900, 800)
    expect(result.current).toBe(true)

    simulateWindowResize(961, 800)
    expect(result.current).toBe(false)
  })
})
