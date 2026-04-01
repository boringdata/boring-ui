import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

import BrowseDrawer from '../BrowseDrawer'

const now = Date.now()
const oneDayMs = 86400000

const mockSessions = [
  { id: 's1', title: 'Revenue Analysis', lastModified: now - 1000, status: 'active' },
  { id: 's2', title: 'Bug Investigation', lastModified: now - 2000, status: 'idle' },
  { id: 's3', title: 'Old Research', lastModified: now - oneDayMs - 1000, status: 'paused' },
]

describe('BrowseDrawer', () => {
  it('when open=false, renders null', () => {
    const { container } = render(
      <BrowseDrawer
        open={false}
        sessions={mockSessions}
        onSwitchSession={vi.fn()}
      />,
    )
    expect(container.firstChild).toBeNull()
  })

  it('shows session history when mode="sessions"', () => {
    render(
      <BrowseDrawer
        open={true}
        sessions={mockSessions}
        onSwitchSession={vi.fn()}
      />,
    )
    expect(screen.getByText('Conversation history')).toBeInTheDocument()
    expect(screen.getByText('Revenue Analysis')).toBeInTheDocument()
    expect(screen.getByTestId('browse-drawer-date-today')).toBeInTheDocument()
    expect(screen.getByTestId('browse-drawer-date-yesterday')).toBeInTheDocument()
  })

  it('clicking a session calls onSwitchSession', () => {
    const onSwitchSession = vi.fn()
    render(
      <BrowseDrawer
        open={true}
        sessions={mockSessions}
        onSwitchSession={onSwitchSession}
      />,
    )
    fireEvent.click(screen.getByTestId('browse-drawer-session-s1'))
    expect(onSwitchSession).toHaveBeenCalledWith('s1')
  })

  it('renders the active session style when the current session is selected', () => {
    render(
      <BrowseDrawer
        open={true}
        sessions={mockSessions}
        activeSessionId="s1"
        onSwitchSession={vi.fn()}
      />,
    )
    expect(screen.getByTestId('browse-drawer-session-s1')).toHaveClass('active')
  })

  it('does not render the user menu in the drawer', () => {
    render(
      <BrowseDrawer
        open={true}
        sessions={mockSessions}
        onSwitchSession={vi.fn()}
      />,
    )
    expect(screen.queryByTestId('mock-user-menu')).not.toBeInTheDocument()
  })
})
