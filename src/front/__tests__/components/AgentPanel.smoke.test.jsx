import React from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

import { CapabilitiesContext } from '../../shared/components/CapabilityGate'
import { resetConfig } from '../../shared/config'
import { getPane } from '../../registry/panes'
import AgentPanel from '../../shared/panels/AgentPanel'

vi.mock('../../shared/providers/pi/PiSessionToolbar', () => ({
  default: ({ panelId }) => <div data-testid="pi-session-toolbar">toolbar:{panelId}</div>,
}))

vi.mock('../../shared/providers/pi/nativeAdapter', () => ({
  default: ({ panelId, sessionBootstrap, initialSessionId }) => (
    <div data-testid="pi-native-adapter">
      native:{panelId}:{sessionBootstrap}:{initialSessionId}
    </div>
  ),
}))
vi.mock('../../shared/providers/pi/backendAdapter', () => ({
  default: ({ panelId, sessionBootstrap, serviceUrl }) => (
    <div data-testid="pi-backend-adapter">
      backend:{panelId}:{sessionBootstrap}:{serviceUrl}
    </div>
  ),
}))
vi.mock('../../shared/components/chat/AiChat', () => ({
  default: () => <div data-testid="ai-chat">ai-sdk-chat</div>,
}))

const renderPanel = ({
  capabilities = { capabilities: { 'agent.chat': true }, services: {} },
  params = {},
} = {}) =>
  render(
    <CapabilitiesContext.Provider value={capabilities}>
      <AgentPanel
        params={{
          panelId: 'agent-panel-1',
          ...params,
        }}
      />
    </CapabilitiesContext.Provider>,
  )

describe('AgentPanel smoke', () => {
  beforeEach(() => {
    vi.stubEnv('VITE_PI_SERVICE_URL', '')
    resetConfig()
  })

  it('keeps the agent pane registry contract stable', () => {
    const config = getPane('agent')

    expect(config).toBeDefined()
    expect(config).toMatchObject({
      id: 'agent',
      essential: false,
      placement: 'right',
      requiresCapabilities: ['agent.chat'],
    })
  })

  it('renders the expected structural shell with the PI native adapter', () => {
    const { container } = renderPanel()

    expect(container.querySelector('.panel-content.agent-panel-content')).toBeInTheDocument()
    expect(container.querySelector('.agent-header')).toBeInTheDocument()
    expect(container.querySelector('.agent-body')).toBeInTheDocument()
    expect(container.querySelector('.agent-instance.active')).toBeInTheDocument()
    expect(screen.getByTestId('agent-panel')).toBeInTheDocument()
    expect(screen.getByTestId('agent-app')).toBeInTheDocument()
    expect(screen.getByTestId('pi-session-toolbar')).toHaveTextContent('toolbar:agent-panel-1')
    expect(screen.getByTestId('pi-native-adapter')).toHaveTextContent('native:agent-panel-1:latest:')
  })

  it('switches to the backend adapter when capabilities advertise backend PI', () => {
    renderPanel({
      capabilities: {
        capabilities: { 'agent.chat': true },
        services: {
          pi: { mode: 'backend', url: 'https://example.test' },
        },
      },
      params: {
        mode: 'backend',
        piSessionBootstrap: 'new',
        piInitialSessionId: 'sess-42',
      },
    })

    expect(screen.queryByTestId('pi-native-adapter')).not.toBeInTheDocument()
    expect(screen.getByTestId('pi-backend-adapter')).toHaveTextContent(
      'backend:agent-panel-1:new:https://example.test',
    )
  })

  it('renders the ai-sdk chat component when the runtime is selected', () => {
    renderPanel({
      params: {
        agentRuntime: 'ai-sdk',
      },
    })

    expect(screen.queryByTestId('pi-session-toolbar')).not.toBeInTheDocument()
    expect(screen.queryByTestId('pi-native-adapter')).not.toBeInTheDocument()
    expect(screen.getByTestId('agent-ai-sdk-app')).toBeInTheDocument()
    expect(screen.getByTestId('ai-chat')).toHaveTextContent('ai-sdk-chat')
  })
})
