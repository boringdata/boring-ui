import React from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

import { CapabilitiesContext } from '../../components/CapabilityGate'
import { getPane } from '../../registry/panes'
import AgentPanel from '../../panels/AgentPanel'
import { getPiServiceUrl, isPiBackendMode } from '../../providers/pi/config'

vi.mock('../../providers/pi/PiSessionToolbar', () => ({
  default: ({ panelId }) => <div data-testid="pi-session-toolbar">toolbar:{panelId}</div>,
}))

vi.mock('../../providers/pi/nativeAdapter', () => ({
  default: ({ panelId }) => <div data-testid="pi-native-adapter">native:{panelId}</div>,
}))

vi.mock('../../providers/pi/backendAdapter', () => ({
  default: ({ panelId, serviceUrl }) => (
    <div data-testid="pi-backend-adapter">
      backend:{panelId}:{serviceUrl}
    </div>
  ),
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

  it('renders the expected structural shell in frontend mode', () => {
    const { container } = renderPanel()

    expect(container.querySelector('.panel-content.terminal-panel-content.agent-panel-content')).toBeInTheDocument()
    expect(container.querySelector('.terminal-header')).toBeInTheDocument()
    expect(container.querySelector('.terminal-body.agent-body')).toBeInTheDocument()
    expect(container.querySelector('.agent-instance.active')).toBeInTheDocument()
    expect(screen.getByTestId('agent-panel')).toBeInTheDocument()
    expect(screen.getByTestId('agent-app')).toBeInTheDocument()
    expect(screen.getByTestId('pi-session-toolbar')).toHaveTextContent('toolbar:agent-panel-1')
    expect(screen.getByTestId('pi-native-adapter')).toHaveTextContent('native:agent-panel-1')
    expect(screen.queryByTestId('pi-backend-adapter')).not.toBeInTheDocument()
  })

  it('detects backend mode only when the pi service advertises backend transport', () => {
    expect(isPiBackendMode({ features: { pi: true }, services: {} })).toBe(false)
    expect(
      isPiBackendMode({
        features: { pi: true },
        services: { pi: { mode: 'BACKEND' } },
      }),
    ).toBe(true)
  })

  it('normalizes the pi service URL from capabilities', () => {
    expect(
      getPiServiceUrl({
        features: { pi: true },
        services: { pi: { mode: 'backend', url: '/w/ws-123' } },
      }),
    ).toBe(`${window.location.origin}/w/ws-123`)
  })
})
