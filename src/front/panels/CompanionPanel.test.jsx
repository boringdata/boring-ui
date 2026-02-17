import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'

// Mock the adapter component
vi.mock('../providers/companion/adapter', () => ({
  default: () => <div data-testid="mock-companion-app">MockCompanionApp</div>,
}))
vi.mock('../providers/companion/EmbeddedSessionToolbar', () => ({
  default: () => <div data-testid="mock-companion-toolbar">MockCompanionToolbar</div>,
}))
vi.mock('../providers/pi/PiSessionToolbar', () => ({
  default: () => <div data-testid="mock-pi-toolbar">MockPiToolbar</div>,
}))
vi.mock('../providers/pi/nativeAdapter', () => ({
  default: () => <div data-testid="mock-pi-native-app">MockPiNativeApp</div>,
}))

// Mock CSS imports
vi.mock('../providers/companion/upstream.css', () => ({}))
vi.mock('../providers/companion/theme-bridge.css', () => ({}))
vi.mock('../providers/companion/overrides.css', () => ({}))

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

  it('renders PI native adapter without companion URL wiring when provider is pi', () => {
    mockCapabilities.services = {}

    render(<CompanionPanel params={{ provider: 'pi' }} />)

    expect(screen.getByTestId('pi-app')).toBeTruthy()
    expect(screen.getByTestId('mock-pi-toolbar')).toBeTruthy()
    expect(screen.getByTestId('mock-pi-native-app')).toBeTruthy()
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

  it('uses dedicated pi backend URL metadata when both provider URLs exist', () => {
    mockCapabilities.services = {
      companion: { url: 'http://localhost:3456' },
      pi: { url: 'http://localhost:8787', mode: 'embedded' },
    }

    render(<CompanionPanel params={{ provider: 'pi' }} />)

    expect(screen.getByTestId('pi-app')).toBeTruthy()
    expect(screen.getByTestId('mock-pi-toolbar')).toBeTruthy()
    expect(screen.getByTestId('mock-pi-native-app')).toBeTruthy()
    expect(screen.getByTestId('pi-app').getAttribute('data-service-url')).toBe('http://localhost:8787')
    expect(mockSetCompanionConfig).not.toHaveBeenCalled()
  })

  it('renders collapsed state with correct test id', () => {
    render(<CompanionPanel params={{ collapsed: true, onToggleCollapse: vi.fn() }} />)

    expect(screen.getByTestId('companion-panel-collapsed')).toBeTruthy()
    expect(screen.queryByTestId('companion-app')).toBeNull()
    expect(screen.queryByTestId('companion-connecting')).toBeNull()
  })

  it('calls toggle callback in collapsed and expanded states', () => {
    const onToggleCollapse = vi.fn()
    const { rerender } = render(<CompanionPanel params={{ collapsed: true, onToggleCollapse }} />)

    fireEvent.click(screen.getByRole('button', { name: 'Expand agent panel' }))
    expect(onToggleCollapse).toHaveBeenCalledTimes(1)

    rerender(<CompanionPanel params={{ collapsed: false, onToggleCollapse }} />)
    fireEvent.click(screen.getByRole('button', { name: 'Collapse agent panel' }))
    expect(onToggleCollapse).toHaveBeenCalledTimes(2)
  })

  it('calls setCompanionConfig before rendering CompanionApp', () => {
    mockCapabilities.services = {
      companion: { url: 'http://localhost:3456' },
    }

    render(<CompanionPanel params={{}} />)

    expect(mockSetCompanionConfig).toHaveBeenCalledTimes(1)
    expect(mockSetCompanionConfig).toHaveBeenCalledWith('http://localhost:3456', '')
    expect(screen.getByTestId('mock-companion-app')).toBeTruthy()
  })
})
