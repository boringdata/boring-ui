/**
 * Unit tests for DockLayout component
 *
 * Tests the panel position configuration to ensure that position values
 * like 'center' don't cause runtime errors with dockview-react.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, waitFor } from '@testing-library/react'
import DockLayout from '../../components/DockLayout'

// Mock dockview-react to avoid DOM-related issues in tests
const mockAddPanel = vi.fn()
const mockFromJSON = vi.fn()
const mockToJSON = vi.fn(() => ({ grid: {}, panels: {} }))
const mockOnDidLayoutChange = vi.fn()

vi.mock('dockview-react', () => ({
  DockviewReact: ({ onReady, components }) => {
    // Simulate the onReady callback with a mock API
    setTimeout(() => {
      onReady({
        api: {
          addPanel: mockAddPanel,
          fromJSON: mockFromJSON,
          toJSON: mockToJSON,
          onDidLayoutChange: mockOnDidLayoutChange,
          getPanel: vi.fn(),
          panels: [],
        },
      })
    }, 0)
    return <div data-testid="dockview-mock">DockviewReact Mock</div>
  },
}))

// Mock CSS import
vi.mock('dockview-react/dist/styles/dockview.css', () => ({}))

describe('DockLayout', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Panel Position Configuration', () => {
    it('handles center position without passing invalid direction', async () => {
      const SimplePanel = () => <div>Test Panel</div>
      const components = { simple: SimplePanel }
      const panels = [
        { id: 'center-panel', component: 'simple', position: 'center' },
      ]

      render(
        <DockLayout
          components={components}
          panels={panels}
          persistLayout={false}
        />
      )

      await waitFor(() => {
        expect(mockAddPanel).toHaveBeenCalled()
      })

      // Verify that addPanel was called without a position property
      // (center position should result in no position config)
      const addPanelCall = mockAddPanel.mock.calls[0][0]
      expect(addPanelCall.id).toBe('center-panel')
      expect(addPanelCall.position).toBeUndefined()
    })

    it('handles left position with correct direction', async () => {
      const SimplePanel = () => <div>Test Panel</div>
      const components = { simple: SimplePanel }
      const panels = [
        { id: 'left-panel', component: 'simple', position: 'left' },
      ]

      render(
        <DockLayout
          components={components}
          panels={panels}
          persistLayout={false}
        />
      )

      await waitFor(() => {
        expect(mockAddPanel).toHaveBeenCalled()
      })

      const addPanelCall = mockAddPanel.mock.calls[0][0]
      expect(addPanelCall.id).toBe('left-panel')
      expect(addPanelCall.position).toEqual({ direction: 'left' })
    })

    it('handles right position with correct direction', async () => {
      const SimplePanel = () => <div>Test Panel</div>
      const components = { simple: SimplePanel }
      const panels = [
        { id: 'right-panel', component: 'simple', position: 'right' },
      ]

      render(
        <DockLayout
          components={components}
          panels={panels}
          persistLayout={false}
        />
      )

      await waitFor(() => {
        expect(mockAddPanel).toHaveBeenCalled()
      })

      const addPanelCall = mockAddPanel.mock.calls[0][0]
      expect(addPanelCall.id).toBe('right-panel')
      expect(addPanelCall.position).toEqual({ direction: 'right' })
    })

    it('handles top position with above direction', async () => {
      const SimplePanel = () => <div>Test Panel</div>
      const components = { simple: SimplePanel }
      const panels = [
        { id: 'top-panel', component: 'simple', position: 'top' },
      ]

      render(
        <DockLayout
          components={components}
          panels={panels}
          persistLayout={false}
        />
      )

      await waitFor(() => {
        expect(mockAddPanel).toHaveBeenCalled()
      })

      const addPanelCall = mockAddPanel.mock.calls[0][0]
      expect(addPanelCall.id).toBe('top-panel')
      expect(addPanelCall.position).toEqual({ direction: 'above' })
    })

    it('handles bottom position with below direction', async () => {
      const SimplePanel = () => <div>Test Panel</div>
      const components = { simple: SimplePanel }
      const panels = [
        { id: 'bottom-panel', component: 'simple', position: 'bottom' },
      ]

      render(
        <DockLayout
          components={components}
          panels={panels}
          persistLayout={false}
        />
      )

      await waitFor(() => {
        expect(mockAddPanel).toHaveBeenCalled()
      })

      const addPanelCall = mockAddPanel.mock.calls[0][0]
      expect(addPanelCall.id).toBe('bottom-panel')
      expect(addPanelCall.position).toEqual({ direction: 'below' })
    })

    it('handles custom position object', async () => {
      const SimplePanel = () => <div>Test Panel</div>
      const components = { simple: SimplePanel }
      const customPosition = { direction: 'right', referencePanel: 'other' }
      const panels = [
        { id: 'custom-panel', component: 'simple', position: customPosition },
      ]

      render(
        <DockLayout
          components={components}
          panels={panels}
          persistLayout={false}
        />
      )

      await waitFor(() => {
        expect(mockAddPanel).toHaveBeenCalled()
      })

      const addPanelCall = mockAddPanel.mock.calls[0][0]
      expect(addPanelCall.id).toBe('custom-panel')
      expect(addPanelCall.position).toEqual(customPosition)
    })

    it('defaults to center position when position is not specified', async () => {
      const SimplePanel = () => <div>Test Panel</div>
      const components = { simple: SimplePanel }
      const panels = [
        { id: 'default-panel', component: 'simple' }, // No position specified
      ]

      render(
        <DockLayout
          components={components}
          panels={panels}
          persistLayout={false}
        />
      )

      await waitFor(() => {
        expect(mockAddPanel).toHaveBeenCalled()
      })

      // Default position should also result in no position config (same as center)
      const addPanelCall = mockAddPanel.mock.calls[0][0]
      expect(addPanelCall.id).toBe('default-panel')
      expect(addPanelCall.position).toBeUndefined()
    })
  })

  describe('Multiple Panels', () => {
    it('creates multiple panels with different positions', async () => {
      const SimplePanel = () => <div>Test Panel</div>
      const components = { simple: SimplePanel }
      const panels = [
        { id: 'left', component: 'simple', position: 'left' },
        { id: 'center', component: 'simple', position: 'center' },
        { id: 'right', component: 'simple', position: 'right' },
      ]

      render(
        <DockLayout
          components={components}
          panels={panels}
          persistLayout={false}
        />
      )

      await waitFor(() => {
        expect(mockAddPanel).toHaveBeenCalledTimes(3)
      })

      // Verify each panel has the correct position
      const calls = mockAddPanel.mock.calls

      const leftCall = calls.find(c => c[0].id === 'left')
      expect(leftCall[0].position).toEqual({ direction: 'left' })

      const centerCall = calls.find(c => c[0].id === 'center')
      expect(centerCall[0].position).toBeUndefined()

      const rightCall = calls.find(c => c[0].id === 'right')
      expect(rightCall[0].position).toEqual({ direction: 'right' })
    })
  })

  describe('Unknown Position', () => {
    it('handles unknown position string by using undefined', async () => {
      const SimplePanel = () => <div>Test Panel</div>
      const components = { simple: SimplePanel }
      const panels = [
        { id: 'unknown-panel', component: 'simple', position: 'unknown-position' },
      ]

      render(
        <DockLayout
          components={components}
          panels={panels}
          persistLayout={false}
        />
      )

      await waitFor(() => {
        expect(mockAddPanel).toHaveBeenCalled()
      })

      // Unknown positions should result in undefined (default placement)
      const addPanelCall = mockAddPanel.mock.calls[0][0]
      expect(addPanelCall.position).toBeUndefined()
    })
  })
})
