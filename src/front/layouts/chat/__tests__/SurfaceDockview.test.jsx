import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'

// Track DockviewReact mock API calls
let mockDockApi
let readyCallback

vi.mock('dockview-react', () => {
  return {
    DockviewReact: function MockDockviewReact({ onReady }) {
      // Store onReady so tests can trigger it
      readyCallback = onReady
      return <div data-testid="mock-dockview-react">DockviewReact</div>
    },
  }
})

// Mock the lazy-loaded EditorPanel
vi.mock('../../../shared/panels/EditorPanel', () => ({
  default: function MockEditorPanel({ params }) {
    return <div data-testid={`editor-${params?.path || 'unknown'}`}>Editor: {params?.path}</div>
  },
}))

// Mock Dockview CSS import (no-op)
vi.mock('dockview-react/dist/styles/dockview.css', () => ({}))

import SurfaceDockview from '../SurfaceDockview'

function createMockDockApi() {
  const panels = new Map()
  const listeners = {
    activePanelChange: [],
    removePanel: [],
    layoutChange: [],
  }

  return {
    panels,
    activePanel: null,

    addPanel: vi.fn(({ id, component, title, params }) => {
      const panel = {
        id,
        component,
        title,
        params,
        api: { setActive: vi.fn() },
      }
      panels.set(id, panel)
      return panel
    }),

    getPanel: vi.fn((id) => panels.get(id) || null),

    removePanel: vi.fn((panel) => {
      panels.delete(panel.id)
      for (const cb of listeners.removePanel) cb(panel)
    }),

    onDidActivePanelChange: vi.fn((cb) => {
      listeners.activePanelChange.push(cb)
      return { dispose: vi.fn() }
    }),

    onDidRemovePanel: vi.fn((cb) => {
      listeners.removePanel.push(cb)
      return { dispose: vi.fn() }
    }),

    onDidLayoutChange: vi.fn((cb) => {
      listeners.layoutChange.push(cb)
      return { dispose: vi.fn() }
    }),

    toJSON: vi.fn(() => ({ panels: [] })),
    fromJSON: vi.fn(),

    // Test helper: simulate user switching active panel
    _triggerActivePanelChange(panel) {
      this.activePanel = panel
      for (const cb of listeners.activePanelChange) cb()
    },
  }
}

describe('SurfaceDockview', () => {
  beforeEach(() => {
    mockDockApi = createMockDockApi()
    readyCallback = null
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  function triggerReady() {
    act(() => {
      readyCallback({ api: mockDockApi })
    })
  }

  it('renders without crashing', () => {
    render(
      <SurfaceDockview
        artifacts={[]}
        activeArtifactId={null}
        onSelectArtifact={vi.fn()}
        onCloseArtifact={vi.fn()}
      />
    )
    expect(screen.getByTestId('surface-dockview')).toBeInTheDocument()
  })

  it('creates a panel for each artifact after Dockview is ready', () => {
    const artifacts = [
      { id: 'art-1', title: 'file1.js', kind: 'code', params: { path: 'src/file1.js' } },
      { id: 'art-2', title: 'file2.js', kind: 'code', params: { path: 'src/file2.js' } },
    ]

    render(
      <SurfaceDockview
        artifacts={artifacts}
        activeArtifactId="art-1"
        onSelectArtifact={vi.fn()}
        onCloseArtifact={vi.fn()}
      />
    )

    triggerReady()

    expect(mockDockApi.addPanel).toHaveBeenCalledTimes(2)
    expect(mockDockApi.addPanel).toHaveBeenCalledWith(
      expect.objectContaining({
        id: 'art-1',
        component: 'editor',
        title: 'file1.js',
        params: expect.objectContaining({ path: 'src/file1.js' }),
      })
    )
    expect(mockDockApi.addPanel).toHaveBeenCalledWith(
      expect.objectContaining({
        id: 'art-2',
        component: 'editor',
        title: 'file2.js',
        params: expect.objectContaining({ path: 'src/file2.js' }),
      })
    )
  })

  it('active artifact panel is focused via setActive', () => {
    const artifacts = [
      { id: 'art-1', title: 'file1.js', kind: 'code', params: { path: 'src/file1.js' } },
    ]

    render(
      <SurfaceDockview
        artifacts={artifacts}
        activeArtifactId="art-1"
        onSelectArtifact={vi.fn()}
        onCloseArtifact={vi.fn()}
      />
    )

    triggerReady()

    // The panel should have been added and then setActive called
    const panel = mockDockApi.panels.get('art-1')
    expect(panel).toBeDefined()
    expect(panel.api.setActive).toHaveBeenCalled()
  })

  it('closing a panel calls onCloseArtifact', () => {
    const onClose = vi.fn()
    const artifacts = [
      { id: 'art-1', title: 'file1.js', kind: 'code', params: { path: 'src/file1.js' } },
    ]

    render(
      <SurfaceDockview
        artifacts={artifacts}
        activeArtifactId="art-1"
        onSelectArtifact={vi.fn()}
        onCloseArtifact={onClose}
      />
    )

    triggerReady()

    // Simulate Dockview removing a panel (e.g., via drag-close or programmatic removal)
    const panel = mockDockApi.panels.get('art-1')
    expect(panel).toBeDefined()

    // Simulate the removePanel event from outside the sync cycle
    act(() => {
      mockDockApi.panels.delete('art-1')
      // Trigger the onDidRemovePanel listener (not during sync)
      mockDockApi.onDidRemovePanel.mock.calls[0][0](panel)
    })

    expect(onClose).toHaveBeenCalledWith('art-1')
  })

  it('removes panels when artifacts are removed from the list', () => {
    const artifacts1 = [
      { id: 'art-1', title: 'file1.js', kind: 'code', params: { path: 'src/file1.js' } },
      { id: 'art-2', title: 'file2.js', kind: 'code', params: { path: 'src/file2.js' } },
    ]
    const artifacts2 = [
      { id: 'art-1', title: 'file1.js', kind: 'code', params: { path: 'src/file1.js' } },
    ]

    const { rerender } = render(
      <SurfaceDockview
        artifacts={artifacts1}
        activeArtifactId="art-1"
        onSelectArtifact={vi.fn()}
        onCloseArtifact={vi.fn()}
      />
    )

    triggerReady()

    expect(mockDockApi.addPanel).toHaveBeenCalledTimes(2)

    // Re-render with art-2 removed
    rerender(
      <SurfaceDockview
        artifacts={artifacts2}
        activeArtifactId="art-1"
        onSelectArtifact={vi.fn()}
        onCloseArtifact={vi.fn()}
      />
    )

    expect(mockDockApi.removePanel).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'art-2' })
    )
  })

  it('restores a saved Dockview layout when provided', () => {
    const artifacts = [
      { id: 'art-1', title: 'file1.js', kind: 'code', params: { path: 'src/file1.js' } },
    ]
    const layout = { grid: { root: { type: 'leaf' } } }

    render(
      <SurfaceDockview
        artifacts={artifacts}
        activeArtifactId="art-1"
        layout={layout}
        onSelectArtifact={vi.fn()}
        onCloseArtifact={vi.fn()}
      />
    )

    triggerReady()

    expect(mockDockApi.fromJSON).toHaveBeenCalledWith(layout)
  })
})
