import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import PiSessionToolbar from './PiSessionToolbar'

const requestPiNewSession = vi.fn()
const requestPiSessionState = vi.fn()
const requestPiSwitchSession = vi.fn()
let stateListener = null

vi.mock('./sessionBus', () => ({
  requestPiNewSession: () => requestPiNewSession(),
  requestPiSessionState: () => requestPiSessionState(),
  requestPiSwitchSession: (...args) => requestPiSwitchSession(...args),
  subscribePiSessionState: (listener) => {
    stateListener = listener
    return () => {
      stateListener = null
    }
  },
}))

describe('PiSessionToolbar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    stateListener = null
  })

  it('requests state on mount', () => {
    render(<PiSessionToolbar />)
    expect(requestPiSessionState).toHaveBeenCalledTimes(1)
  })

  it('creates a new PI session on + click', () => {
    render(<PiSessionToolbar panelId="pi-agent" onSplitPanel={vi.fn()} />)

    fireEvent.click(screen.getByTestId('pi-session-new'))

    expect(requestPiNewSession).toHaveBeenCalledTimes(1)
  })

  it('renders sessions and switches by id', () => {
    render(<PiSessionToolbar />)
    act(() => {
      stateListener?.({
        currentSessionId: 's-1',
        sessions: [
          { id: 's-1', title: 'Session 1' },
          { id: 's-2', title: 'Session 2' },
        ],
      })
    })

    fireEvent.change(screen.getByTestId('pi-session-select'), { target: { value: 's-2' } })
    expect(requestPiSwitchSession).toHaveBeenCalledWith('s-2')
  })
})
