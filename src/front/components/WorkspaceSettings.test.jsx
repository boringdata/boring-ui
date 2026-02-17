/**
 * WorkspaceSettings page component unit tests.
 *
 * Bead: bd-223o.14.3 (H3)
 *
 * Validates:
 *   - Renders loading state initially.
 *   - Renders workspace info after load.
 *   - Workspace name inline edit flow.
 *   - Runtime status badge renders correct state.
 *   - Members list renders with status badges.
 *   - Invite form opens and submits.
 *   - Remove member sends DELETE request.
 *   - Back button triggers navigation.
 *   - Not-found state displays error.
 */

import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup, waitFor, act } from '@testing-library/react'
import WorkspaceSettings from './WorkspaceSettings.jsx'

// ── Fetch mock ──────────────────────────────────────────────────────

const WORKSPACE = {
  workspace_id: 'ws_abc123',
  name: 'My Workspace',
  app_id: 'boring-ui',
  created_by: 'user_1',
  created_at: '2026-01-15T10:00:00Z',
  updated_at: '2026-01-15T10:00:00Z',
}

const RUNTIME = {
  runtime_state: 'ready',
}

const MEMBERS = [
  { member_id: 1, email: 'alice@example.com', role: 'admin', status: 'active', user_id: 'user_1' },
  { member_id: 2, email: 'bob@example.com', role: 'admin', status: 'pending', user_id: null },
]

const mockFetch = (responses = {}) => {
  const defaultResponses = {
    '/workspaces/ws_abc123/runtime': { ok: true, data: RUNTIME },
    '/workspaces/ws_abc123/members': { ok: true, data: { members: MEMBERS } },
    '/workspaces/ws_abc123': { ok: true, data: WORKSPACE },
  }
  const merged = { ...defaultResponses, ...responses }

  return vi.fn((url, init) => {
    // Match against URL substrings — patterns are checked in order,
    // longer/more-specific patterns must come first.
    const match = Object.entries(merged).find(([pattern]) => url.includes(pattern))

    if (match) {
      const [, response] = match
      if (!response.ok) {
        return Promise.resolve({
          ok: false,
          status: response.status || 404,
          json: () => Promise.resolve(response.data || {}),
        })
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve(response.data),
      })
    }

    return Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
    })
  })
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

// =====================================================================
// Loading and render
// =====================================================================

describe('WorkspaceSettings — loading', () => {
  it('renders loading state initially', () => {
    globalThis.fetch = mockFetch()
    render(<WorkspaceSettings workspaceId="ws_abc123" />)
    expect(screen.getByText(/Loading workspace settings/)).toBeTruthy()
  })

  it('renders workspace info after load', async () => {
    globalThis.fetch = mockFetch()
    render(<WorkspaceSettings workspaceId="ws_abc123" />)
    await waitFor(() => {
      expect(screen.getByTestId('workspace-name-display')).toBeTruthy()
    })
    expect(screen.getByTestId('workspace-name-display').textContent).toBe('My Workspace')
    expect(screen.getByTestId('workspace-id').textContent).toBe('ws_abc123')
  })

  it('renders not-found when workspace load fails', async () => {
    globalThis.fetch = mockFetch({
      '/workspaces/ws_abc123/runtime': { ok: true, data: RUNTIME },
      '/workspaces/ws_abc123/members': { ok: true, data: { members: [] } },
      '/workspaces/ws_abc123': {
        ok: false,
        status: 404,
        data: { error: 'workspace_not_found' },
      },
    })
    render(<WorkspaceSettings workspaceId="ws_abc123" />)
    await waitFor(() => {
      expect(screen.getByText('Workspace not found.')).toBeTruthy()
    })
  })
})

// =====================================================================
// Workspace name edit
// =====================================================================

describe('WorkspaceSettings — name edit', () => {
  it('opens edit on pencil click', async () => {
    globalThis.fetch = mockFetch()
    render(<WorkspaceSettings workspaceId="ws_abc123" />)
    await waitFor(() => screen.getByTestId('workspace-name-edit'))
    fireEvent.click(screen.getByTestId('workspace-name-edit'))
    expect(screen.getByTestId('workspace-name-input')).toBeTruthy()
  })

  it('cancels edit on X click', async () => {
    globalThis.fetch = mockFetch()
    render(<WorkspaceSettings workspaceId="ws_abc123" />)
    await waitFor(() => screen.getByTestId('workspace-name-edit'))
    fireEvent.click(screen.getByTestId('workspace-name-edit'))
    fireEvent.click(screen.getByTestId('workspace-name-cancel'))
    expect(screen.queryByTestId('workspace-name-input')).toBeNull()
  })

  it('saves new name on check click', async () => {
    const fetchFn = mockFetch()
    globalThis.fetch = fetchFn
    render(<WorkspaceSettings workspaceId="ws_abc123" />)
    await waitFor(() => screen.getByTestId('workspace-name-edit'))

    fireEvent.click(screen.getByTestId('workspace-name-edit'))
    const input = screen.getByTestId('workspace-name-input')
    fireEvent.change(input, { target: { value: 'New Name' } })
    fireEvent.click(screen.getByTestId('workspace-name-save'))

    await waitFor(() => {
      const patchCalls = fetchFn.mock.calls.filter(
        ([, init]) => init?.method === 'PATCH',
      )
      expect(patchCalls.length).toBeGreaterThan(0)
    })
  })
})

// =====================================================================
// Runtime status
// =====================================================================

describe('WorkspaceSettings — runtime', () => {
  it('renders runtime ready state', async () => {
    globalThis.fetch = mockFetch()
    render(<WorkspaceSettings workspaceId="ws_abc123" />)
    await waitFor(() => screen.getByTestId('runtime-state'))
    expect(screen.getByTestId('runtime-state').textContent).toBe('Ready')
  })

  it('renders runtime error state', async () => {
    globalThis.fetch = mockFetch({
      '/workspaces/ws_abc123/runtime': {
        ok: true,
        data: { runtime_state: 'error' },
      },
    })
    render(<WorkspaceSettings workspaceId="ws_abc123" />)
    await waitFor(() => screen.getByTestId('runtime-state'))
    expect(screen.getByTestId('runtime-state').textContent).toBe('Error')
  })

  it('renders runtime provisioning state', async () => {
    globalThis.fetch = mockFetch({
      '/workspaces/ws_abc123/runtime': {
        ok: true,
        data: { runtime_state: 'provisioning' },
      },
    })
    render(<WorkspaceSettings workspaceId="ws_abc123" />)
    await waitFor(() => screen.getByTestId('runtime-state'))
    expect(screen.getByTestId('runtime-state').textContent).toBe('Provisioning')
  })
})

// =====================================================================
// Members
// =====================================================================

describe('WorkspaceSettings — members', () => {
  it('renders members list', async () => {
    globalThis.fetch = mockFetch()
    render(<WorkspaceSettings workspaceId="ws_abc123" />)
    await waitFor(() => screen.getByTestId('members-list'))
    expect(screen.getByText('alice@example.com')).toBeTruthy()
    expect(screen.getByText('bob@example.com')).toBeTruthy()
    expect(screen.getByText('Active')).toBeTruthy()
    expect(screen.getByText('Pending')).toBeTruthy()
  })

  it('opens invite form on invite click', async () => {
    globalThis.fetch = mockFetch()
    render(<WorkspaceSettings workspaceId="ws_abc123" />)
    await waitFor(() => screen.getByTestId('invite-toggle'))
    fireEvent.click(screen.getByTestId('invite-toggle'))
    expect(screen.getByTestId('invite-form')).toBeTruthy()
    expect(screen.getByTestId('invite-email-input')).toBeTruthy()
  })

  it('sends invite on submit', async () => {
    const fetchFn = mockFetch()
    globalThis.fetch = fetchFn
    render(<WorkspaceSettings workspaceId="ws_abc123" />)
    await waitFor(() => screen.getByTestId('invite-toggle'))

    fireEvent.click(screen.getByTestId('invite-toggle'))
    const input = screen.getByTestId('invite-email-input')
    fireEvent.change(input, { target: { value: 'carol@example.com' } })
    fireEvent.click(screen.getByTestId('invite-submit'))

    await waitFor(() => {
      const postCalls = fetchFn.mock.calls.filter(
        ([url, init]) => init?.method === 'POST' && url.includes('/members'),
      )
      expect(postCalls.length).toBeGreaterThan(0)
    })
  })

  it('sends remove on trash click', async () => {
    const fetchFn = mockFetch()
    globalThis.fetch = fetchFn
    render(<WorkspaceSettings workspaceId="ws_abc123" />)
    await waitFor(() => screen.getByTestId('remove-member-1'))

    fireEvent.click(screen.getByTestId('remove-member-1'))

    await waitFor(() => {
      const deleteCalls = fetchFn.mock.calls.filter(
        ([, init]) => init?.method === 'DELETE',
      )
      expect(deleteCalls.length).toBeGreaterThan(0)
    })
  })
})

// =====================================================================
// Navigation
// =====================================================================

describe('WorkspaceSettings — navigation', () => {
  it('calls onBack when back button clicked', async () => {
    globalThis.fetch = mockFetch()
    const onBack = vi.fn()
    render(<WorkspaceSettings workspaceId="ws_abc123" onBack={onBack} />)
    await waitFor(() => screen.getByTestId('settings-back'))
    fireEvent.click(screen.getByTestId('settings-back'))
    expect(onBack).toHaveBeenCalledOnce()
  })
})
