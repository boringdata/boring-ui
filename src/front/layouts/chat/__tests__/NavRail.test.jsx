import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

vi.mock('../../../shared/components/UserMenu', () => ({
  default: () => <div data-testid="mock-user-menu">user-menu</div>,
}))

import NavRail from '../NavRail'

describe('NavRail', () => {
  it('renders brand icon', () => {
    render(<NavRail onDestinationChange={vi.fn()} onNewChat={vi.fn()} />)
    const brand = screen.getByTestId('nav-rail-brand')
    expect(brand).toBeInTheDocument()
    expect(brand).toHaveTextContent('B')
  })

  it('renders new chat button', () => {
    render(<NavRail onDestinationChange={vi.fn()} onNewChat={vi.fn()} />)
    const newChat = screen.getByTestId('nav-rail-new-chat')
    expect(newChat).toBeInTheDocument()
  })

  it('renders sessions button', () => {
    render(<NavRail onDestinationChange={vi.fn()} onNewChat={vi.fn()} />)
    const sessions = screen.getByTestId('nav-rail-history')
    expect(sessions).toBeInTheDocument()
  })

  it('clicking sessions toggles active state', () => {
    const onChange = vi.fn()
    render(
      <NavRail
        activeDestination={null}
        onDestinationChange={onChange}
        onNewChat={vi.fn()}
      />
    )
    const sessions = screen.getByTestId('nav-rail-history')
    fireEvent.click(sessions)
    expect(onChange).toHaveBeenCalledWith('sessions')
  })

  it('clicking same active destination calls onDestinationChange(null) (close)', () => {
    const onChange = vi.fn()
    render(
      <NavRail
        activeDestination="sessions"
        onDestinationChange={onChange}
        onNewChat={vi.fn()}
      />
    )
    const sessions = screen.getByTestId('nav-rail-history')
    fireEvent.click(sessions)
    expect(onChange).toHaveBeenCalledWith(null)
  })

  it('clicking new chat calls onNewChat', () => {
    const onNewChat = vi.fn()
    render(
      <NavRail
        onDestinationChange={vi.fn()}
        onNewChat={onNewChat}
      />
    )
    const newChat = screen.getByTestId('nav-rail-new-chat')
    fireEvent.click(newChat)
    expect(onNewChat).toHaveBeenCalled()
  })

  it('has role="navigation" with accessible label', () => {
    render(<NavRail onDestinationChange={vi.fn()} onNewChat={vi.fn()} />)
    const nav = screen.getByRole('navigation', { name: /main navigation/i })
    expect(nav).toBeInTheDocument()
  })

  it('renders the user menu at the bottom of the rail when shell context is provided', () => {
    render(
      <NavRail
        onDestinationChange={vi.fn()}
        onNewChat={vi.fn()}
        shellContext={{ userEmail: 'local@example.com', onOpenUserSettings: vi.fn() }}
      />
    )

    expect(screen.getByTestId('nav-rail-footer')).toBeInTheDocument()
    expect(screen.getByTestId('mock-user-menu')).toBeInTheDocument()
  })
})
