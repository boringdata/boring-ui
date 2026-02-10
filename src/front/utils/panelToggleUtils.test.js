import { describe, it, expect, vi } from 'vitest'
import { createPanelToggle } from './panelToggleUtils'

// Mock the layout module
vi.mock('../layout', () => ({
  savePanelSizes: vi.fn(),
  saveCollapsedState: vi.fn(),
}))

import { savePanelSizes, saveCollapsedState } from '../layout'

describe('createPanelToggle', () => {
  const makeOptions = (overrides = {}) => ({
    panelId: 'filetree',
    panelKey: 'filetree',
    dimension: 'width',
    dockApi: {
      getPanel: vi.fn().mockReturnValue({
        group: { api: { width: 300, height: 200 } },
      }),
    },
    isCollapsed: false,
    setCollapsed: vi.fn((fn) => fn({ filetree: false, terminal: false })),
    panelSizesRef: { current: { filetree: 280 } },
    collapsedThreshold: 48,
    storagePrefix: 'test',
    ...overrides,
  })

  it('returns a function', () => {
    const toggle = createPanelToggle(makeOptions())
    expect(typeof toggle).toBe('function')
  })

  it('captures size before collapsing when panel is expanded', () => {
    const opts = makeOptions()
    const toggle = createPanelToggle(opts)
    toggle()

    // Should have saved the current width (300) to panelSizesRef
    expect(opts.panelSizesRef.current.filetree).toBe(300)
    expect(savePanelSizes).toHaveBeenCalled()
  })

  it('does not capture size when panel is already collapsed', () => {
    const opts = makeOptions({ isCollapsed: true })
    const toggle = createPanelToggle(opts)
    toggle()

    // Should not have called savePanelSizes
    expect(savePanelSizes).not.toHaveBeenCalled()
  })

  it('toggles collapsed state', () => {
    const opts = makeOptions()
    const toggle = createPanelToggle(opts)
    toggle()

    expect(opts.setCollapsed).toHaveBeenCalled()
    // The updater function should flip the filetree state
    const updater = opts.setCollapsed.mock.calls[0][0]
    const result = updater({ filetree: false, terminal: false })
    expect(result.filetree).toBe(true)
  })

  it('persists collapsed state', () => {
    const opts = makeOptions()
    const toggle = createPanelToggle(opts)
    toggle()

    expect(saveCollapsedState).toHaveBeenCalled()
  })

  it('uses height dimension for bottom panels', () => {
    const opts = makeOptions({
      panelId: 'shell',
      panelKey: 'shell',
      dimension: 'height',
      dockApi: {
        getPanel: vi.fn().mockReturnValue({
          group: { api: { width: 300, height: 250 } },
        }),
      },
      panelSizesRef: { current: { shell: 200 } },
    })
    const toggle = createPanelToggle(opts)
    toggle()

    // Should capture height (250), not width
    expect(opts.panelSizesRef.current.shell).toBe(250)
  })

  it('skips capture if size below threshold', () => {
    const opts = makeOptions({
      dockApi: {
        getPanel: vi.fn().mockReturnValue({
          group: { api: { width: 30 } },
        }),
      },
      collapsedThreshold: 48,
    })
    savePanelSizes.mockClear()
    const toggle = createPanelToggle(opts)
    toggle()

    expect(savePanelSizes).not.toHaveBeenCalled()
  })

  it('handles missing dockApi gracefully', () => {
    const opts = makeOptions({ dockApi: null })
    const toggle = createPanelToggle(opts)
    toggle() // Should not throw
    expect(opts.setCollapsed).toHaveBeenCalled()
  })
})
