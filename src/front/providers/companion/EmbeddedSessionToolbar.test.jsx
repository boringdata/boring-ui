import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

const mockCreateSession = vi.fn()
const mockListSessions = vi.fn()
const mockConnectSession = vi.fn()
const mockDisconnectSession = vi.fn()

vi.mock('./upstream/api', () => ({
  api: {
    createSession: (...args) => mockCreateSession(...args),
    listSessions: (...args) => mockListSessions(...args),
  },
}))

vi.mock('./upstream/ws', () => ({
  connectSession: (...args) => mockConnectSession(...args),
  disconnectSession: (...args) => mockDisconnectSession(...args),
}))

const mockState = {
  currentSessionId: 's1',
  sdkSessions: [],
  sessionNames: new Map(),
  setCurrentSession: vi.fn((id) => {
    mockState.currentSessionId = id
  }),
  setSdkSessions: vi.fn((sessions) => {
    mockState.sdkSessions = sessions
  }),
}

vi.mock('./upstream/store', () => ({
  useStore: (selector) => selector(mockState),
}))

import EmbeddedSessionToolbar from './EmbeddedSessionToolbar'

describe('EmbeddedSessionToolbar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockState.currentSessionId = 's1'
    mockState.sdkSessions = [
      { sessionId: 's1', createdAt: 10, cwd: '/tmp/project-a', archived: false, model: 'claude' },
      { sessionId: 's2', createdAt: 20, cwd: '/tmp/project-b', archived: false, model: 'claude' },
      { sessionId: 's3', createdAt: 30, cwd: '/tmp/project-c', archived: true, model: 'claude' },
    ]
    mockState.sessionNames = new Map([['s2', 'Named Session']])
  })

  it('renders active sessions and switches session from dropdown', () => {
    render(<EmbeddedSessionToolbar />)

    const select = screen.getByTestId('companion-session-select')
    const options = screen.getAllByRole('option')
    expect(options).toHaveLength(2) // archived session excluded
    expect(options[0].textContent).toBe('Named Session') // newer session first

    fireEvent.change(select, { target: { value: 's2' } })

    expect(mockDisconnectSession).toHaveBeenCalledWith('s1')
    expect(mockState.setCurrentSession).toHaveBeenCalledWith('s2')
    expect(mockConnectSession).toHaveBeenCalledWith('s2')
  })

  it('creates a new session with + and refreshes list', async () => {
    mockCreateSession.mockResolvedValue({ sessionId: 's-new' })
    mockListSessions.mockResolvedValue([
      { sessionId: 's-new', createdAt: 100, cwd: '/tmp/new', archived: false, model: 'claude' },
    ])

    render(<EmbeddedSessionToolbar />)

    fireEvent.click(screen.getByTestId('companion-session-new'))

    await waitFor(() => {
      expect(mockCreateSession).toHaveBeenCalledTimes(1)
      expect(mockDisconnectSession).toHaveBeenCalledWith('s1')
      expect(mockState.setCurrentSession).toHaveBeenCalledWith('s-new')
      expect(mockConnectSession).toHaveBeenCalledWith('s-new')
      expect(mockListSessions).toHaveBeenCalledTimes(1)
      expect(mockState.setSdkSessions).toHaveBeenCalledTimes(1)
    })
  })
})
