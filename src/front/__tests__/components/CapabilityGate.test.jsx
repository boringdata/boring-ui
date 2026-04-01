import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

// Mock the pane registry to avoid transitive dependency chains (FileTree → @tanstack/react-query etc.)
vi.mock('../../registry/panes', () => ({
  getPane: vi.fn((id) => {
    if (id === 'test-pane') {
      return { id: 'test-pane', title: 'Test Pane', requiresCapabilities: ['workspace.files'] }
    }
    return null
  }),
  checkRequirements: vi.fn((id, capabilities) => {
    if (id === 'test-pane') {
      return !!capabilities?.capabilities?.['workspace.files']
    }
    return false
  }),
}))

import {
  CapabilitiesContext,
  CapabilitiesStatusContext,
  createCapabilityGatedPane,
} from '../../shared/components/CapabilityGate'

function DummyPane() {
  return <div data-testid="dummy-pane">Pane content</div>
}

const GatedPane = createCapabilityGatedPane('test-pane', DummyPane)

function renderGated({ capabilities, pending }) {
  return render(
    <CapabilitiesStatusContext.Provider value={{ pending }}>
      <CapabilitiesContext.Provider value={capabilities}>
        <GatedPane />
      </CapabilitiesContext.Provider>
    </CapabilitiesStatusContext.Provider>,
  )
}

describe('CapabilityGate', () => {
  it('shows loading state when capabilities are pending', () => {
    renderGated({ capabilities: null, pending: true })

    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.getByText('Test Pane Loading')).toBeInTheDocument()
    expect(screen.queryByTestId('dummy-pane')).not.toBeInTheDocument()
  })

  it('renders the wrapped component when capabilities are met', () => {
    renderGated({
      capabilities: { capabilities: { 'workspace.files': true } },
      pending: false,
    })

    expect(screen.getByTestId('dummy-pane')).toBeInTheDocument()
    expect(screen.getByText('Pane content')).toBeInTheDocument()
  })

  it('shows error state when required capabilities are missing', () => {
    renderGated({
      capabilities: { capabilities: {} },
      pending: false,
    })

    expect(screen.getByText('Test Pane Unavailable')).toBeInTheDocument()
    expect(screen.getByText('workspace.files')).toBeInTheDocument()
    expect(screen.queryByTestId('dummy-pane')).not.toBeInTheDocument()
  })

  it('renders component when no capabilities context (backwards compat)', () => {
    render(
      <CapabilitiesStatusContext.Provider value={{ pending: false }}>
        <CapabilitiesContext.Provider value={null}>
          <GatedPane />
        </CapabilitiesContext.Provider>
      </CapabilitiesStatusContext.Provider>,
    )

    expect(screen.getByTestId('dummy-pane')).toBeInTheDocument()
  })

  it('transitions from loading to rendered when pending clears', () => {
    const { rerender } = renderGated({ capabilities: null, pending: true })

    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.queryByTestId('dummy-pane')).not.toBeInTheDocument()

    rerender(
      <CapabilitiesStatusContext.Provider value={{ pending: false }}>
        <CapabilitiesContext.Provider value={{ capabilities: { 'workspace.files': true } }}>
          <GatedPane />
        </CapabilitiesContext.Provider>
      </CapabilitiesStatusContext.Provider>,
    )

    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(screen.getByTestId('dummy-pane')).toBeInTheDocument()
  })
})
