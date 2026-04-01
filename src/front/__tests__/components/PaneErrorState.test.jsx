import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import PaneErrorState from '../../shared/components/PaneErrorState'

describe('PaneErrorState', () => {
  it('renders unavailable message with title', () => {
    render(<PaneErrorState paneId="terminal" paneTitle="Terminal" />)

    expect(screen.getByText('Terminal Unavailable')).toBeInTheDocument()
    expect(screen.getByText(/requires a service/)).toBeInTheDocument()
  })

  it('falls back to paneId when title is missing', () => {
    render(<PaneErrorState paneId="terminal" />)

    expect(screen.getByText('terminal Unavailable')).toBeInTheDocument()
  })

  it('lists missing features', () => {
    render(
      <PaneErrorState
        paneId="terminal"
        paneTitle="Terminal"
        missingFeatures={['pty', 'shell']}
      />,
    )

    expect(screen.getByText('pty')).toBeInTheDocument()
    expect(screen.getByText('shell')).toBeInTheDocument()
  })

  it('lists missing routers', () => {
    render(
      <PaneErrorState
        paneId="agent"
        paneTitle="Agent"
        missingRouters={['agent_router']}
      />,
    )

    expect(screen.getByText('agent_router')).toBeInTheDocument()
  })

  it('shows hint about API server', () => {
    render(<PaneErrorState paneId="test" />)

    expect(screen.getByText(/check that the backend/i)).toBeInTheDocument()
  })
})
