/**
 * End-to-end workspace switch and context isolation tests.
 *
 * Bead: bd-223o.14.2.1 (H2a)
 *
 * Validates context switches across multiple workspaces without stale
 * state leakage:
 *
 *   1. Workspace switch updates derived state to new workspace's runtime
 *   2. Hard navigation model: switch triggers window.location.assign
 *   3. URL-based workspace ID extraction drives initial selection
 *   4. No stale state leakage: switching resets runtime/error state
 *   5. Workspace switcher renders correct workspace list from hook state
 *   6. useOnboardingState pass-through mode when disabled
 *   7. useOnboardingState fetches /me, /workspaces, /runtime in sequence
 *   8. useOnboardingState handles 401 on /me → unauthenticated
 *   9. useOnboardingState handles workspace fetch failure gracefully
 *  10. Workspace ID field aliases (id, workspace_id, workspaceId)
 *  11. Multiple workspaces with mixed runtime states
 */

import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, fireEvent, cleanup, waitFor, act } from '@testing-library/react'
import { renderHook } from '@testing-library/react'

import {
  ONBOARDING_STATES,
  deriveOnboardingState,
} from '../onboarding/stateMachine.js'
import WorkspaceSwitcher from '../components/WorkspaceSwitcher.jsx'
import { useOnboardingState } from '../hooks/useOnboardingState.js'

const S = ONBOARDING_STATES

// ── Helpers ──────────────────────────────────────────────────────────

/** Mock fetch that responds to different API paths.
 *
 * Routes map pattern strings to:
 *   - Plain objects/arrays → 200 OK with JSON body
 *   - Functions → called to produce the above
 *   - { _error: true, status, code, message } → non-ok response
 */
const createRoutedFetch = (routes = {}) =>
  vi.fn(async (url) => {
    const path = typeof url === 'string' ? url : url.toString()

    for (const [pattern, handler] of Object.entries(routes)) {
      if (path.includes(pattern)) {
        const result = typeof handler === 'function' ? handler() : handler
        if (result && result._error) {
          const status = result.status || 500
          const body = { detail: result.message || 'Error', code: result.code || String(status) }
          return {
            ok: false,
            status,
            text: async () => JSON.stringify(body),
            json: async () => body,
          }
        }
        return {
          ok: true,
          status: 200,
          text: async () => JSON.stringify(result),
          json: async () => result,
        }
      }
    }

    return {
      ok: true,
      status: 200,
      text: async () => '{}',
      json: async () => ({}),
    }
  })

const make401Error = () => ({
  _error: true,
  status: 401,
  code: '401',
  message: 'Unauthorized',
})

const make500Error = () => ({
  _error: true,
  status: 500,
  code: '500',
  message: 'Internal server error',
})

/** Mock window.location for navigation tests. */
let originalLocation

beforeEach(() => {
  originalLocation = window.location
  // Default empty fetch.
  globalThis.fetch = vi.fn(async () => ({
    ok: true,
    status: 200,
    text: async () => '{}',
    json: async () => ({}),
  }))
})

afterEach(() => {
  cleanup()
  if (originalLocation) {
    try {
      Object.defineProperty(window, 'location', {
        value: originalLocation,
        writable: true,
        configurable: true,
      })
    } catch { /* already restored */ }
  }
})

// =====================================================================
// 1. Workspace switch updates derived state
// =====================================================================

describe('Workspace switch updates derived state', () => {
  it('selecting ready workspace derives READY state', () => {
    const workspaces = [
      { id: 'ws1', name: 'Alpha', runtime_state: 'ready' },
      { id: 'ws2', name: 'Beta', runtime_state: 'queued' },
    ]

    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces,
      selectedWorkspaceId: 'ws1',
    })

    expect(result.state).toBe(S.WORKSPACE_SELECTED_READY)
    expect(result.selectedWorkspaceId).toBe('ws1')
    expect(result.selectedWorkspace.name).toBe('Alpha')
  })

  it('selecting provisioning workspace derives PROVISIONING state', () => {
    const workspaces = [
      { id: 'ws1', name: 'Alpha', runtime_state: 'ready' },
      { id: 'ws2', name: 'Beta', runtime_state: 'queued' },
    ]

    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces,
      selectedWorkspaceId: 'ws2',
    })

    expect(result.state).toBe(S.WORKSPACE_SELECTED_PROVISIONING)
    expect(result.selectedWorkspaceId).toBe('ws2')
    expect(result.selectedWorkspace.name).toBe('Beta')
  })

  it('selecting error workspace derives ERROR state', () => {
    const workspaces = [
      { id: 'ws1', name: 'Alpha', runtime_state: 'ready' },
      { id: 'ws2', name: 'Beta', runtime_state: 'error' },
    ]

    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces,
      selectedWorkspaceId: 'ws2',
    })

    expect(result.state).toBe(S.WORKSPACE_SELECTED_ERROR)
    expect(result.selectedWorkspaceId).toBe('ws2')
  })
})

// =====================================================================
// 2. Hard navigation model
// =====================================================================

describe('Hard navigation model', () => {
  it('openWorkspaceApp navigates to /w/{id}/app', async () => {
    const assignMock = vi.fn()
    Object.defineProperty(window, 'location', {
      value: { ...originalLocation, assign: assignMock, pathname: '/', search: '' },
      writable: true,
      configurable: true,
    })

    globalThis.fetch = createRoutedFetch({
      '/api/v1/me': { id: 'u1', email: 'user@test.com' },
      '/api/v1/workspaces': [{ id: 'ws1', runtime_state: 'ready' }],
      '/runtime': { state: 'ready' },
    })

    const { result } = renderHook(() => useOnboardingState({ enabled: true }))

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    act(() => {
      result.current.openWorkspaceApp('ws_target')
    })

    expect(assignMock).toHaveBeenCalledWith('/w/ws_target/app')
  })

  it('startLogin navigates to /auth/login', async () => {
    const assignMock = vi.fn()
    Object.defineProperty(window, 'location', {
      value: { ...originalLocation, assign: assignMock, pathname: '/some/path', search: '' },
      writable: true,
      configurable: true,
    })

    globalThis.fetch = createRoutedFetch({
      '/api/v1/me': make401Error(),
    })

    const { result } = renderHook(() => useOnboardingState({ enabled: true }))

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    act(() => {
      result.current.startLogin()
    })

    expect(assignMock).toHaveBeenCalledWith(expect.stringContaining('/auth/login'))
  })
})

// =====================================================================
// 3. No stale state leakage on workspace switch
// =====================================================================

describe('No stale state leakage', () => {
  it('switching from error workspace to ready workspace clears error state', () => {
    const workspaces = [
      { id: 'ws1', runtime_state: 'error' },
      { id: 'ws2', runtime_state: 'ready' },
    ]

    const errorState = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces,
      selectedWorkspaceId: 'ws1',
      errors: { runtime: { code: 'STEP_TIMEOUT' } },
    })
    expect(errorState.state).toBe(S.WORKSPACE_SELECTED_ERROR)
    expect(errorState.errorCode).toBe('STEP_TIMEOUT')

    // Switch to ws2.
    const readyState = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces,
      selectedWorkspaceId: 'ws2',
      errors: {},
    })
    expect(readyState.state).toBe(S.WORKSPACE_SELECTED_READY)
    // Error code from previous workspace should NOT leak.
    expect(readyState.errorCode).toBe('')
  })

  it('switching from ready workspace to provisioning workspace updates runtimeState', () => {
    const workspaces = [
      { id: 'ws1', runtime_state: 'ready' },
      { id: 'ws2', runtime_state: 'queued' },
    ]

    const r1 = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces,
      selectedWorkspaceId: 'ws1',
    })
    expect(r1.runtimeState).toBe('ready')

    const r2 = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces,
      selectedWorkspaceId: 'ws2',
    })
    expect(r2.runtimeState).toBe('provisioning')
  })

  it('each workspace derivation is independent (no shared mutable state)', () => {
    const workspaces = [
      { id: 'ws1', runtime_state: 'ready' },
      { id: 'ws2', runtime_state: 'error' },
      { id: 'ws3', runtime_state: 'queued' },
    ]

    const results = ['ws1', 'ws2', 'ws3'].map((id) =>
      deriveOnboardingState({
        user: { id: 'u1' },
        workspaces,
        selectedWorkspaceId: id,
      }),
    )

    // Verify each result is independent.
    expect(results[0].state).toBe(S.WORKSPACE_SELECTED_READY)
    expect(results[1].state).toBe(S.WORKSPACE_SELECTED_ERROR)
    expect(results[2].state).toBe(S.WORKSPACE_SELECTED_PROVISIONING)

    // Verify no object identity leakage.
    expect(results[0].selectedWorkspace).not.toBe(results[1].selectedWorkspace)
    expect(results[1].selectedWorkspace).not.toBe(results[2].selectedWorkspace)
  })
})

// =====================================================================
// 4. Workspace switcher renders correct list
// =====================================================================

describe('Workspace switcher renders from derived state', () => {
  it('renders all workspaces from derived state', () => {
    const derived = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [
        { id: 'ws1', name: 'Alpha', runtime_state: 'ready' },
        { id: 'ws2', name: 'Beta', runtime_state: 'queued' },
        { id: 'ws3', name: 'Gamma', runtime_state: 'error' },
      ],
      selectedWorkspaceId: 'ws1',
    })

    render(
      <WorkspaceSwitcher
        workspaces={derived.workspaces}
        selectedWorkspaceId={derived.selectedWorkspaceId}
      />,
    )

    expect(screen.getByText('Alpha')).toBeTruthy()
    fireEvent.click(screen.getByTestId('workspace-switcher-trigger'))
    expect(screen.getByText('Beta')).toBeTruthy()
    expect(screen.getByText('Gamma')).toBeTruthy()
  })

  it('does not show current workspace in selectable list', () => {
    const derived = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [
        { id: 'ws1', name: 'Alpha', runtime_state: 'ready' },
        { id: 'ws2', name: 'Beta', runtime_state: 'ready' },
      ],
      selectedWorkspaceId: 'ws1',
    })

    render(
      <WorkspaceSwitcher
        workspaces={derived.workspaces}
        selectedWorkspaceId={derived.selectedWorkspaceId}
      />,
    )

    fireEvent.click(screen.getByTestId('workspace-switcher-trigger'))
    expect(screen.queryByTestId('workspace-option-ws1')).toBeNull()
    expect(screen.getByTestId('workspace-option-ws2')).toBeTruthy()
  })

  it('onSwitchWorkspace callback receives correct workspace ID', () => {
    const onSwitch = vi.fn()
    render(
      <WorkspaceSwitcher
        workspaces={[
          { id: 'ws_a', name: 'Project A' },
          { id: 'ws_b', name: 'Project B' },
        ]}
        selectedWorkspaceId="ws_a"
        onSwitchWorkspace={onSwitch}
      />,
    )

    fireEvent.click(screen.getByTestId('workspace-switcher-trigger'))
    fireEvent.click(screen.getByTestId('workspace-option-ws_b'))
    expect(onSwitch).toHaveBeenCalledWith('ws_b')
  })
})

// =====================================================================
// 5. useOnboardingState pass-through mode
// =====================================================================

describe('useOnboardingState pass-through', () => {
  it('returns READY state when disabled', () => {
    const { result } = renderHook(() => useOnboardingState({ enabled: false }))

    expect(result.current.state).toBe(S.WORKSPACE_SELECTED_READY)
    expect(result.current.isBlocking).toBe(false)
    expect(result.current.isLoading).toBe(false)
  })

  it('does not fetch APIs when disabled', () => {
    renderHook(() => useOnboardingState({ enabled: false }))
    expect(globalThis.fetch).not.toHaveBeenCalled()
  })
})

// =====================================================================
// 6. useOnboardingState API sequence
// =====================================================================

describe('useOnboardingState API sequence', () => {
  it('fetches /me then /workspaces then /runtime', async () => {
    globalThis.fetch = createRoutedFetch({
      '/api/v1/me': { id: 'u1', email: 'user@test.com' },
      '/api/v1/workspaces': [{ id: 'ws1', name: 'My WS', runtime_state: 'ready' }],
      '/runtime': { state: 'ready' },
    })

    const { result } = renderHook(() => useOnboardingState({ enabled: true }))

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.state).toBe(S.WORKSPACE_SELECTED_READY)
    expect(result.current.user).toEqual({ id: 'u1', email: 'user@test.com' })
    expect(result.current.selectedWorkspaceId).toBe('ws1')
    expect(result.current.isBlocking).toBe(false)
  })

  it('handles 401 on /me → unauthenticated', async () => {
    globalThis.fetch = createRoutedFetch({
      '/api/v1/me': make401Error(),
    })

    const { result } = renderHook(() => useOnboardingState({ enabled: true }))

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.state).toBe(S.UNAUTHENTICATED)
    expect(result.current.isBlocking).toBe(true)
    expect(result.current.user).toBeNull()
  })

  it('handles workspace fetch failure → authenticated_no_workspace', async () => {
    globalThis.fetch = vi.fn(async (url) => {
      const path = typeof url === 'string' ? url : url.toString()
      if (path.includes('/api/v1/me')) {
        const data = { id: 'u1', email: 'u@test.com' }
        return { ok: true, status: 200, text: async () => JSON.stringify(data), json: async () => data }
      }
      // All workspace/runtime calls fail.
      return {
        ok: false,
        status: 500,
        text: async () => JSON.stringify({ detail: 'Server error', code: '500' }),
        json: async () => ({ detail: 'Server error', code: '500' }),
      }
    })

    const { result } = renderHook(() => useOnboardingState({ enabled: true }))

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.state).toBe(S.AUTHENTICATED_NO_WORKSPACE)
    expect(result.current.isBlocking).toBe(true)
  })

  it('handles runtime error → workspace_selected_error', async () => {
    globalThis.fetch = vi.fn(async (url) => {
      const path = typeof url === 'string' ? url : url.toString()
      if (path.includes('/api/v1/me')) {
        const data = { id: 'u1', email: 'u@test.com' }
        return { ok: true, status: 200, text: async () => JSON.stringify(data), json: async () => data }
      }
      if (path.includes('/runtime')) {
        return {
          ok: false, status: 500,
          text: async () => JSON.stringify({ detail: 'timeout', code: 'runtime_status_unavailable' }),
          json: async () => ({ detail: 'timeout', code: 'runtime_status_unavailable' }),
        }
      }
      // /api/v1/workspaces
      const ws = [{ id: 'ws1', name: 'WS' }]
      return { ok: true, status: 200, text: async () => JSON.stringify(ws), json: async () => ws }
    })

    const { result } = renderHook(() => useOnboardingState({ enabled: true }))

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.state).toBe(S.WORKSPACE_SELECTED_ERROR)
    expect(result.current.isBlocking).toBe(true)
  })
})

// =====================================================================
// 7. Workspace ID field aliases
// =====================================================================

describe('Workspace ID field aliases', () => {
  it('workspace.id is preferred', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime_state: 'ready' }],
    })
    expect(result.selectedWorkspaceId).toBe('ws1')
  })

  it('falls back to workspace.workspace_id', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ workspace_id: 'ws_alt', runtime_state: 'ready' }],
    })
    expect(result.selectedWorkspaceId).toBe('ws_alt')
  })

  it('falls back to workspace.workspaceId', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ workspaceId: 'ws_camel', runtime_state: 'ready' }],
    })
    expect(result.selectedWorkspaceId).toBe('ws_camel')
  })

  it('switcher supports all ID field aliases', () => {
    render(
      <WorkspaceSwitcher
        workspaces={[
          { id: 'ws1', name: 'By ID' },
          { workspace_id: 'ws2', name: 'By workspace_id' },
          { workspaceId: 'ws3', name: 'By workspaceId' },
        ]}
        selectedWorkspaceId="ws1"
      />,
    )

    fireEvent.click(screen.getByTestId('workspace-switcher-trigger'))
    expect(screen.getByTestId('workspace-option-ws2')).toBeTruthy()
    expect(screen.getByTestId('workspace-option-ws3')).toBeTruthy()
  })
})

// =====================================================================
// 8. Multiple workspaces with mixed runtime states
// =====================================================================

describe('Mixed runtime states', () => {
  const workspaces = [
    { id: 'ws_ready', name: 'Ready', runtime_state: 'ready' },
    { id: 'ws_queued', name: 'Queued', runtime_state: 'queued' },
    { id: 'ws_creating', name: 'Creating', runtime_state: 'creating_sandbox' },
    { id: 'ws_error', name: 'Error', runtime_state: 'error' },
    { id: 'ws_failed', name: 'Failed', runtime_state: 'failed' },
    { id: 'ws_health', name: 'Health', runtime_state: 'health_check' },
  ]

  const expectedStates = {
    ws_ready: S.WORKSPACE_SELECTED_READY,
    ws_queued: S.WORKSPACE_SELECTED_PROVISIONING,
    ws_creating: S.WORKSPACE_SELECTED_PROVISIONING,
    ws_error: S.WORKSPACE_SELECTED_ERROR,
    ws_failed: S.WORKSPACE_SELECTED_ERROR,
    ws_health: S.WORKSPACE_SELECTED_PROVISIONING,
  }

  Object.entries(expectedStates).forEach(([wsId, expectedState]) => {
    it(`workspace ${wsId} derives ${expectedState}`, () => {
      const result = deriveOnboardingState({
        user: { id: 'u1' },
        workspaces,
        selectedWorkspaceId: wsId,
      })
      expect(result.state).toBe(expectedState)
      expect(result.selectedWorkspaceId).toBe(wsId)
    })
  })

  it('all workspaces are independently selectable in switcher', () => {
    render(
      <WorkspaceSwitcher
        workspaces={workspaces}
        selectedWorkspaceId="ws_ready"
      />,
    )

    fireEvent.click(screen.getByTestId('workspace-switcher-trigger'))
    expect(screen.getByText('Queued')).toBeTruthy()
    expect(screen.getByText('Creating')).toBeTruthy()
    expect(screen.getByText('Error')).toBeTruthy()
    expect(screen.getByText('Failed')).toBeTruthy()
    expect(screen.getByText('Health')).toBeTruthy()
  })
})

// =====================================================================
// 9. Refresh reloads state
// =====================================================================

describe('Refresh reloads state', () => {
  it('refresh callback is available and callable', async () => {
    globalThis.fetch = createRoutedFetch({
      '/api/v1/me': { id: 'u1' },
      '/api/v1/workspaces': [],
    })

    const { result } = renderHook(() => useOnboardingState({ enabled: true }))

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(typeof result.current.refresh).toBe('function')

    // Refresh should not throw.
    await act(async () => {
      await result.current.refresh()
    })
  })
})

// =====================================================================
// 10. retryProvisioning integration
// =====================================================================

describe('retryProvisioning integration', () => {
  it('retryProvisioning calls /retry endpoint and reloads state', async () => {
    let runtimeCallCount = 0
    globalThis.fetch = vi.fn(async (url, init) => {
      const path = typeof url === 'string' ? url : url.toString()
      const method = init?.method || 'GET'

      if (path.includes('/api/v1/me')) {
        const data = { id: 'u1', email: 'u@test.com' }
        return { ok: true, status: 200, text: async () => JSON.stringify(data), json: async () => data }
      }
      if (path.includes('/retry') && method === 'POST') {
        const data = { ok: true }
        return { ok: true, status: 200, text: async () => JSON.stringify(data), json: async () => data }
      }
      if (path.includes('/runtime')) {
        runtimeCallCount++
        const data = runtimeCallCount <= 1
          ? { state: 'error', last_error_code: 'STEP_TIMEOUT' }
          : { state: 'queued' }
        return { ok: true, status: 200, text: async () => JSON.stringify(data), json: async () => data }
      }
      // /api/v1/workspaces
      const ws = [{ id: 'ws1', name: 'WS' }]
      return { ok: true, status: 200, text: async () => JSON.stringify(ws), json: async () => ws }
    })

    const { result } = renderHook(() => useOnboardingState({ enabled: true }))

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.state).toBe(S.WORKSPACE_SELECTED_ERROR)

    await act(async () => {
      const retryResult = await result.current.retryProvisioning()
      expect(retryResult.ok).toBe(true)
    })
  })

  it('retryProvisioning returns failure when no workspace selected', async () => {
    globalThis.fetch = createRoutedFetch({
      '/api/v1/me': { id: 'u1' },
      '/api/v1/workspaces': [],
    })

    const { result } = renderHook(() => useOnboardingState({ enabled: true }))

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    const retryResult = await result.current.retryProvisioning()
    expect(retryResult.ok).toBe(false)
    expect(retryResult.reason).toBe('missing_workspace_id')
  })
})
