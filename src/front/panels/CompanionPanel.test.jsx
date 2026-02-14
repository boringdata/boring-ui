import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

// Mock the upstream App component
vi.mock('../providers/companion/upstream/App', () => ({
  default: () => <div data-testid="mock-companion-app">MockCompanionApp</div>,
}))

// Mock CSS imports
vi.mock('../providers/companion/upstream.css', () => ({}))
vi.mock('../providers/companion/theme-bridge.css', () => ({}))

// Mock config module
const mockSetCompanionConfig = vi.fn()
vi.mock('../providers/companion/config', () => ({
  setCompanionConfig: (...args) => mockSetCompanionConfig(...args),
}))

// Mock CapabilityGate context
const mockCapabilities = { services: {} }
vi.mock('../components/CapabilityGate', () => ({
  useCapabilitiesContext: () => mockCapabilities,
}))

import CompanionPanel from './CompanionPanel'

describe('CompanionPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockCapabilities.services = {}
  })

  it('shows connecting state when companion URL is not available', () => {
    mockCapabilities.services = {}

    render(<CompanionPanel params={{}} />)

    expect(screen.getByTestId('companion-connecting')).toBeTruthy()
    expect(screen.queryByTestId('companion-app')).toBeNull()
    expect(mockSetCompanionConfig).not.toHaveBeenCalled()
  })

  it('renders CompanionApp when companion URL is available', () => {
    mockCapabilities.services = {
      companion: { url: 'http://localhost:3456' },
    }

    render(<CompanionPanel params={{}} />)

    expect(screen.getByTestId('companion-app')).toBeTruthy()
    expect(screen.queryByTestId('companion-connecting')).toBeNull()
    expect(mockSetCompanionConfig).toHaveBeenCalledWith('http://localhost:3456', '')
  })

  it('renders collapsed state with correct test id', () => {
    render(<CompanionPanel params={{ collapsed: true, onToggleCollapse: vi.fn() }} />)

    expect(screen.getByTestId('companion-panel-collapsed')).toBeTruthy()
    expect(screen.queryByTestId('companion-app')).toBeNull()
    expect(screen.queryByTestId('companion-connecting')).toBeNull()
  })

  it('calls setCompanionConfig before rendering CompanionApp', () => {
    mockCapabilities.services = {
      companion: { url: 'http://localhost:3456' },
    }

    render(<CompanionPanel params={{}} />)

    // setCompanionConfig should have been called (via useMemo, before render)
    expect(mockSetCompanionConfig).toHaveBeenCalledTimes(1)
    expect(mockSetCompanionConfig).toHaveBeenCalledWith('http://localhost:3456', '')
    // And CompanionApp should be rendered
    expect(screen.getByTestId('mock-companion-app')).toBeTruthy()
  })
})
