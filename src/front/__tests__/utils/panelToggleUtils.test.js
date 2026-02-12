import { describe, it, expect, vi } from 'vitest'

import { capturePanelSize, createPanelToggle } from '../../utils/panelToggleUtils'

describe('capturePanelSize', () => {
  it('returns group size for requested dimension', () => {
    const dockApi = {
      getGroup: vi.fn().mockReturnValue({
        api: { width: 420, height: 180 },
      }),
    }

    expect(capturePanelSize(dockApi, 'filetree-group', 'width')).toBe(420)
    expect(capturePanelSize(dockApi, 'shell-group', 'height')).toBe(180)
  })

  it('returns null when group does not exist', () => {
    const dockApi = { getGroup: vi.fn().mockReturnValue(null) }
    expect(capturePanelSize(dockApi, 'missing-group', 'width')).toBeNull()
  })

  it('returns null when dockApi is missing', () => {
    expect(capturePanelSize(null, 'filetree-group', 'width')).toBeNull()
  })
})

describe('createPanelToggle', () => {
  it('captures size and toggles when expanding -> collapsed', () => {
    const setCollapsed = vi.fn()
    const savePanelSizes = vi.fn()
    const panelSizesRef = { current: { filetree: 280 } }
    const dockApi = {
      getGroup: vi.fn().mockReturnValue({ api: { width: 360 } }),
    }

    const toggle = createPanelToggle({
      dockApi,
      groupId: 'filetree-group',
      panelKey: 'filetree',
      dimension: 'width',
      collapsed: { filetree: false },
      setCollapsed,
      panelSizesRef,
      collapsedSize: 48,
      savePanelSizes,
    })

    toggle()

    expect(panelSizesRef.current.filetree).toBe(360)
    expect(savePanelSizes).toHaveBeenCalledWith(panelSizesRef.current)
    expect(setCollapsed).toHaveBeenCalledTimes(1)

    const updater = setCollapsed.mock.calls[0][0]
    expect(updater({ filetree: false }).filetree).toBe(true)
  })

  it('does not overwrite stored size when already collapsed', () => {
    const setCollapsed = vi.fn()
    const savePanelSizes = vi.fn()
    const panelSizesRef = { current: { filetree: 300 } }
    const dockApi = {
      getGroup: vi.fn().mockReturnValue({ api: { width: 500 } }),
    }

    const toggle = createPanelToggle({
      dockApi,
      groupId: 'filetree-group',
      panelKey: 'filetree',
      collapsed: { filetree: true },
      setCollapsed,
      panelSizesRef,
      collapsedSize: 48,
      savePanelSizes,
    })

    toggle()

    expect(panelSizesRef.current.filetree).toBe(300)
    expect(savePanelSizes).not.toHaveBeenCalled()
    expect(setCollapsed).toHaveBeenCalledTimes(1)

    const updater = setCollapsed.mock.calls[0][0]
    expect(updater({ filetree: true }).filetree).toBe(false)
  })

  it('handles missing panel group without throwing', () => {
    const setCollapsed = vi.fn()
    const savePanelSizes = vi.fn()
    const panelSizesRef = { current: { terminal: 400 } }
    const dockApi = {
      getGroup: vi.fn().mockReturnValue(null),
    }

    const toggle = createPanelToggle({
      dockApi,
      groupId: 'terminal-group',
      panelKey: 'terminal',
      collapsed: { terminal: false },
      setCollapsed,
      panelSizesRef,
      collapsedSize: 48,
      savePanelSizes,
    })

    expect(() => toggle()).not.toThrow()
    expect(savePanelSizes).not.toHaveBeenCalled()
    expect(setCollapsed).toHaveBeenCalledTimes(1)
  })

  it('still toggles when dockApi is missing (size capture skipped)', () => {
    const setCollapsed = vi.fn()

    const toggle = createPanelToggle({
      dockApi: null,
      groupId: 'filetree-group',
      panelKey: 'filetree',
      collapsed: { filetree: false },
      setCollapsed,
      panelSizesRef: { current: {} },
      savePanelSizes: vi.fn(),
    })

    expect(() => toggle()).not.toThrow()
    expect(setCollapsed).toHaveBeenCalledTimes(1)
    const updater = setCollapsed.mock.calls[0][0]
    expect(updater({ filetree: false }).filetree).toBe(true)
  })
})
