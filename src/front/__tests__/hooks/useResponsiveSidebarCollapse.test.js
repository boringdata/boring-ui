import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { useState } from 'react'
import useResponsiveSidebarCollapse from '../../shared/hooks/useResponsiveSidebarCollapse'

describe('useResponsiveSidebarCollapse', () => {
  function useHarness({ isNarrowViewport, storagePrefix, initialCollapsed = false }) {
    const [collapsed, setCollapsed] = useState({ filetree: initialCollapsed })
    const clearResponsiveFiletreeAutoCollapse = useResponsiveSidebarCollapse({
      isNarrowViewport,
      storagePrefix,
      collapsedFiletree: collapsed.filetree,
      setCollapsed,
    })

    return {
      collapsed,
      setCollapsed,
      clearResponsiveFiletreeAutoCollapse,
    }
  }

  it('auto-collapses the filetree when entering a narrow viewport', async () => {
    const { result, rerender } = renderHook(useHarness, {
      initialProps: {
        isNarrowViewport: false,
        storagePrefix: 'boring-ui-u-user-1',
      },
    })

    expect(result.current.collapsed.filetree).toBe(false)

    rerender({
      isNarrowViewport: true,
      storagePrefix: 'boring-ui-u-user-1',
    })

    await waitFor(() => {
      expect(result.current.collapsed.filetree).toBe(true)
    })
  })

  it('restores the filetree when leaving a narrow viewport after an auto-collapse', async () => {
    const { result, rerender } = renderHook(useHarness, {
      initialProps: {
        isNarrowViewport: true,
        storagePrefix: 'boring-ui-u-user-1',
      },
    })

    await waitFor(() => {
      expect(result.current.collapsed.filetree).toBe(true)
    })

    rerender({
      isNarrowViewport: false,
      storagePrefix: 'boring-ui-u-user-1',
    })

    await waitFor(() => {
      expect(result.current.collapsed.filetree).toBe(false)
    })
  })

  it('does not force a restore after the user clears the auto-collapse state', async () => {
    const { result, rerender } = renderHook(useHarness, {
      initialProps: {
        isNarrowViewport: true,
        storagePrefix: 'boring-ui-u-user-1',
      },
    })

    await waitFor(() => {
      expect(result.current.collapsed.filetree).toBe(true)
    })

    act(() => {
      result.current.clearResponsiveFiletreeAutoCollapse()
    })

    rerender({
      isNarrowViewport: false,
      storagePrefix: 'boring-ui-u-user-1',
    })

    expect(result.current.collapsed.filetree).toBe(true)
  })
})
