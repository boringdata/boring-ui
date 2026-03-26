import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { resetConfig } from '../config'
import { CapabilitiesContext } from '../components/CapabilityGate'

vi.mock('../providers/pi/PiSessionToolbar', () => ({
  default: () => <div data-testid="mock-pi-toolbar">MockPiToolbar</div>,
}))
vi.mock('../providers/pi/nativeAdapter', () => ({
  default: ({ panelId, sessionBootstrap, initialSessionId }) => (
    <div data-testid="mock-pi-native-app">
      {`MockPiNativeApp:${panelId}:${sessionBootstrap}:${initialSessionId}`}
    </div>
  ),
}))
vi.mock('../providers/pi/backendAdapter', () => ({
  default: ({ panelId, sessionBootstrap, serviceUrl }) => (
    <div data-testid="mock-pi-backend-app">
      {`MockPiBackendApp:${panelId}:${sessionBootstrap}:${serviceUrl}`}
    </div>
  ),
}))
vi.mock('../components/chat/AiChat', () => ({
  default: () => <div data-testid="mock-ai-chat">MockAiChat</div>,
}))

import AgentPanel from './AgentPanel'

const renderPanel = (params = {}, capabilities = null) =>
  render(
    <CapabilitiesContext.Provider value={capabilities}>
      <AgentPanel params={params} />
    </CapabilitiesContext.Provider>,
  )

describe('AgentPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    resetConfig()
  })

  it('renders the native PI adapter by default', () => {
    renderPanel({ panelId: 'panel-1' })

    expect(screen.getByTestId('agent-panel')).toBeTruthy()
    expect(screen.getByTestId('mock-pi-toolbar')).toBeTruthy()
    expect(screen.getByTestId('mock-pi-native-app')).toBeTruthy()
    expect(screen.getByTestId('mock-pi-native-app')).toHaveTextContent('MockPiNativeApp:panel-1:latest:')
  })

  it('still renders the native PI adapter when backend mode params are present', () => {
    renderPanel({ panelId: 'panel-2', mode: 'backend' })

    expect(screen.getByTestId('agent-panel')).toBeTruthy()
    expect(screen.getByTestId('mock-pi-toolbar')).toBeTruthy()
    expect(screen.getByTestId('mock-pi-native-app')).toBeTruthy()
    expect(screen.getByTestId('mock-pi-native-app')).toHaveTextContent('MockPiNativeApp:panel-2:latest:')
  })

  it('forwards session bootstrap props to the native adapter', () => {
    renderPanel({
      panelId: 'panel-3',
      mode: 'backend',
      piSessionBootstrap: 'new',
      piInitialSessionId: 'sess-123',
    })

    expect(screen.getByTestId('mock-pi-native-app')).toHaveTextContent('MockPiNativeApp:panel-3:new:sess-123')
  })

  it('switches to the backend PI adapter when capabilities advertise backend mode', () => {
    renderPanel(
      {
        panelId: 'panel-4',
        piSessionBootstrap: 'new',
      },
      {
        services: {
          pi: {
            mode: 'backend',
            url: 'https://example.test',
          },
        },
      },
    )

    expect(screen.queryByTestId('mock-pi-native-app')).toBeNull()
    expect(screen.getByTestId('mock-pi-backend-app')).toHaveTextContent(
      'MockPiBackendApp:panel-4:new:https://example.test',
    )
  })

  it('renders the ai-sdk chat component instead of PI when ai-sdk runtime is selected', () => {
    renderPanel({ panelId: 'panel-5', agentRuntime: 'ai-sdk' })

    expect(screen.getByTestId('agent-panel')).toBeTruthy()
    expect(screen.queryByTestId('mock-pi-toolbar')).toBeNull()
    expect(screen.queryByTestId('mock-pi-native-app')).toBeNull()
    expect(screen.getByTestId('agent-ai-sdk-app')).toBeTruthy()
    expect(screen.getByTestId('mock-ai-chat')).toHaveTextContent('MockAiChat')
  })
})
