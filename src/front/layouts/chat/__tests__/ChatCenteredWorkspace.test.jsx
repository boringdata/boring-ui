import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

const { useChatMock, openArtifactMock } = vi.hoisted(() => ({
  useChatMock: vi.fn(() => ({
    messages: [],
    sendMessage: vi.fn(),
    status: 'ready',
    stop: vi.fn(),
    error: undefined,
  })),
  openArtifactMock: vi.fn(),
}))

vi.mock('@ai-sdk/react', () => ({
  useChat: useChatMock,
}))

vi.mock('../../../shared/providers/agent/useAgentTransport', () => ({
  useAgentTransport: vi.fn(() => ({
    transport: {
      sendMessages: vi.fn(),
      reconnectToStream: vi.fn(),
      resetAgent: vi.fn(),
    },
    mode: 'frontend',
  })),
}))

vi.mock('../ChatStage', () => ({
  default: function MockChatStage({ sessionTitle }) {
    return <div data-testid="chat-stage">{sessionTitle}</div>
  },
}))

vi.mock('../NavRail', () => ({
  default: function MockNavRail({ activeDestination, onDestinationChange }) {
    return (
      <nav data-testid="nav-rail" role="navigation" aria-label="Main navigation">
        <button type="button" onClick={() => onDestinationChange('sessions')}>
          Sessions
        </button>
        <span data-testid="active-destination">{activeDestination || 'none'}</span>
      </nav>
    )
  },
}))

vi.mock('../BrowseDrawer', () => ({
  default: function MockBrowseDrawer({ open, sessions = [] }) {
    return open ? <div data-testid="browse-drawer">{sessions.length >= 0 ? 'sessions' : ''}</div> : null
  },
}))

vi.mock('../SurfaceShell', () => ({
  default: function MockSurfaceShell({ open }) {
    return (
      <div
        data-testid="surface-shell"
        style={{ display: open ? 'flex' : 'none' }}
      >
        SurfaceShell
      </div>
    )
  },
}))

vi.mock('../hooks/useSessionState', () => ({
  useSessionState: () => ({
    activeSessionId: 'session-12345678',
    activeSession: { id: 'session-12345678', title: 'Fix auth refresh', draft: '', messages: [] },
    sessions: [],
    switchSession: vi.fn(),
    createNewSession: vi.fn(),
    ensureSession: vi.fn(),
    updateSessionDraft: vi.fn(),
    updateSessionMessages: vi.fn(),
  }),
}))

vi.mock('../hooks/useArtifactController', () => ({
  useArtifactController: () => ({
    activeArtifactId: null,
    artifacts: new Map(),
    orderedIds: [],
    open: openArtifactMock,
    focus: vi.fn(),
    close: vi.fn(),
    setSurfaceOpen: vi.fn(),
  }),
}))

vi.mock('../../../shared/hooks/useChatMetrics', () => ({
  ChatMetricsProvider: ({ children }) => <>{children}</>,
}))

vi.mock('../../../shared/hooks/useReducedMotion', () => ({
  useReducedMotion: () => false,
}))

vi.mock('../hooks/useShellPersistence', () => ({
  useShellPersistence: vi.fn(),
}))

vi.mock('../hooks/useShellStatePublisher', () => ({
  useShellStatePublisher: vi.fn(),
}))

import ChatCenteredWorkspace from '../ChatCenteredWorkspace'

describe('ChatCenteredWorkspace', () => {
  beforeEach(() => {
    useChatMock.mockReturnValue({
      messages: [],
      sendMessage: vi.fn(),
      status: 'ready',
      stop: vi.fn(),
      error: undefined,
    })
    openArtifactMock.mockReset()
  })

  it('renders without crashing', () => {
    render(<ChatCenteredWorkspace />)
    expect(screen.getByTestId('chat-centered-workspace')).toBeInTheDocument()
  })

  it('contains a nav rail region and a main stage region', () => {
    render(<ChatCenteredWorkspace />)
    expect(screen.getByRole('navigation', { name: /main navigation/i })).toBeInTheDocument()
    expect(screen.getByRole('main')).toBeInTheDocument()
  })

  it('renders the active session title in the chat stage', () => {
    render(<ChatCenteredWorkspace />)
    expect(screen.getByTestId('chat-stage')).toHaveTextContent('Fix auth refresh')
  })

  it('opens the browse drawer when the rail selects a destination', () => {
    render(<ChatCenteredWorkspace />)
    fireEvent.click(screen.getByRole('button', { name: 'Sessions' }))
    expect(screen.getByTestId('browse-drawer')).toHaveTextContent('sessions')
  })

  it('does not render DockviewReact', () => {
    render(<ChatCenteredWorkspace />)
    expect(screen.queryByTestId('dockview')).not.toBeInTheDocument()
  })

  it('surface is hidden by default until explicitly opened', () => {
    render(<ChatCenteredWorkspace />)
    expect(screen.getByTestId('surface-shell')).toHaveStyle({ display: 'none' })
  })

  it('auto-opens file-backed artifacts from completed tool results', () => {
    useChatMock.mockReturnValue({
      messages: [
        {
          id: 'assistant-1',
          role: 'assistant',
          parts: [
            {
              type: 'tool-result',
              toolCallId: 'tool-1',
              toolName: 'open_file',
              input: { path: 'workbench.feret-overview.json' },
              output: { opened: true, path: 'workbench.feret-overview.json' },
            },
          ],
        },
      ],
      sendMessage: vi.fn(),
      status: 'ready',
      stop: vi.fn(),
      error: undefined,
    })

    render(<ChatCenteredWorkspace />)

    expect(openArtifactMock).toHaveBeenCalledWith(
      expect.objectContaining({
        canonicalKey: 'workbench.feret-overview.json',
        params: expect.objectContaining({ path: 'workbench.feret-overview.json' }),
      }),
    )
  })

  it('auto-opens file-backed artifacts from AI SDK static tool parts', () => {
    useChatMock.mockReturnValue({
      messages: [
        {
          id: 'assistant-2',
          role: 'assistant',
          parts: [
            {
              type: 'tool-open_file',
              toolCallId: 'tool-2',
              state: 'output-available',
              input: { path: 'workbench.feret-overview.json' },
              output: { opened: true, path: 'workbench.feret-overview.json' },
            },
          ],
        },
      ],
      sendMessage: vi.fn(),
      status: 'ready',
      stop: vi.fn(),
      error: undefined,
    })

    render(<ChatCenteredWorkspace />)

    expect(openArtifactMock).toHaveBeenCalledWith(
      expect.objectContaining({
        canonicalKey: 'workbench.feret-overview.json',
        params: expect.objectContaining({ path: 'workbench.feret-overview.json' }),
      }),
    )
  })
})
