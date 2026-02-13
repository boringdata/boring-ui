/**
 * Cross-cutting frontend UX flow integration tests.
 *
 * Bead: bd-cckb (H6)
 *
 * Validates multi-component integration flows that span the full
 * onboarding → workspace → error recovery lifecycle:
 *
 *   1. Onboarding gate + state machine: derived states render correct gate UI
 *   2. Error pipeline: apiErrors → ProvisioningError → OnboardingStateGate
 *   3. Workspace switch + navigation: switcher triggers hard navigation
 *   4. Branding resolution through the gate: workspace > app > local > fallback
 *   5. Retry recovery: error state → retry → provisioning → ready
 *   6. Auth session expiry: 401 resets gate to unauthenticated
 *   7. Cross-workspace isolation: switching workspace resets runtime state
 *   8. Error code mapping: backend codes propagate through full UX stack
 *   9. State machine transition completeness across all gate UI states
 *  10. Provisioning error embedded in gate with branding visible
 *  11. Loading states: provisioning spinner and refresh messaging
 */

import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, fireEvent, cleanup, waitFor, act } from '@testing-library/react'

import {
  ONBOARDING_STATES,
  ONBOARDING_EVENTS,
  advanceOnboardingState,
  deriveOnboardingState,
} from '../onboarding/stateMachine.js'
import { resolveApiError, resolveFromError } from '../utils/apiErrors.js'
import OnboardingStateGate from '../components/OnboardingStateGate.jsx'
import WorkspaceSwitcher from '../components/WorkspaceSwitcher.jsx'

const S = ONBOARDING_STATES
const E = ONBOARDING_EVENTS

// ── Helpers ──────────────────────────────────────────────────────────

/** Build a mock machine object that OnboardingStateGate expects. */
const makeMachine = (overrides = {}) => ({
  state: S.UNAUTHENTICATED,
  eventTrace: [],
  user: null,
  workspaces: [],
  selectedWorkspace: null,
  selectedWorkspaceId: null,
  runtime: null,
  runtimeState: '',
  isLoading: false,
  errors: {},
  errorCode: '',
  startLogin: vi.fn(),
  startCreateWorkspace: vi.fn(),
  openWorkspaceApp: vi.fn(),
  retryProvisioning: vi.fn(),
  refresh: vi.fn(),
  ...overrides,
})

/** Derive state and merge into machine shape with action stubs. */
const deriveMachine = (snapshot, actions = {}) => {
  const derived = deriveOnboardingState(snapshot)
  return makeMachine({ ...derived, ...actions })
}

/** Mock fetch to return a JSON response. */
const mockFetch = (data, status = 200) =>
  vi.fn(() =>
    Promise.resolve({
      ok: status >= 200 && status < 300,
      status,
      json: () => Promise.resolve(data),
      text: () => Promise.resolve(JSON.stringify(data)),
    }),
  )

beforeEach(() => {
  // Default: app-config fetch returns empty (falls back to local config).
  globalThis.fetch = mockFetch({})
})

afterEach(cleanup)

// =====================================================================
// 1. Onboarding gate renders correct UI for each derived state
// =====================================================================

describe('OnboardingGate + state machine integration', () => {
  it('renders sign-in gate for unauthenticated state', () => {
    const machine = deriveMachine({ user: null, workspaces: [] })
    render(<OnboardingStateGate machine={machine} />)

    expect(screen.getByText('Sign in required')).toBeTruthy()
    expect(screen.getByText('Sign in')).toBeTruthy()
  })

  it('renders create-workspace gate for authenticated-no-workspace', () => {
    const machine = deriveMachine({
      user: { id: 'u1' },
      workspaces: [],
    })
    render(<OnboardingStateGate machine={machine} />)

    expect(screen.getByText('Create your first workspace')).toBeTruthy()
    expect(screen.getByText('Create workspace')).toBeTruthy()
  })

  it('renders provisioning spinner for workspace-selected-provisioning', () => {
    const machine = deriveMachine({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', name: 'My Workspace', runtime_state: 'queued' }],
    })
    render(<OnboardingStateGate machine={machine} />)

    expect(screen.getByText('Provisioning workspace runtime')).toBeTruthy()
    expect(screen.getByText(/Provisioning My Workspace/)).toBeTruthy()
  })

  it('renders ready gate for workspace-selected-ready', () => {
    const machine = deriveMachine({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', name: 'Ready WS', runtime_state: 'ready' }],
    })
    render(<OnboardingStateGate machine={machine} />)

    expect(screen.getByText('Workspace ready')).toBeTruthy()
    expect(screen.getByText('Open workspace app')).toBeTruthy()
  })

  it('renders error gate with provisioning error for workspace-selected-error', () => {
    const machine = deriveMachine({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', name: 'Error WS', runtime_state: 'error' }],
      errors: { runtime: { code: 'STEP_TIMEOUT' } },
    })
    render(<OnboardingStateGate machine={machine} />)

    expect(screen.getByText('Provisioning failed')).toBeTruthy()
    expect(screen.getByTestId('provisioning-error')).toBeTruthy()
    expect(screen.getByText('Provisioning step timed out')).toBeTruthy()
  })
})

// =====================================================================
// 2. Error pipeline: apiErrors → ProvisioningError → Gate
// =====================================================================

describe('Error pipeline integration', () => {
  it('backend STEP_TIMEOUT propagates through derive → gate → ProvisioningError', () => {
    const machine = deriveMachine({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime_state: 'error' }],
      runtime: { last_error_code: 'STEP_TIMEOUT', last_error_detail: 'Step X exceeded 120s' },
    })
    render(<OnboardingStateGate machine={machine} />)

    expect(screen.getByTestId('prov-error-title').textContent).toBe('Provisioning step timed out')
    expect(screen.getByTestId('prov-error-detail').textContent).toBe('Step X exceeded 120s')
    expect(screen.getByTestId('prov-error-guidance').textContent).toContain('transient infrastructure')
  })

  it('backend ARTIFACT_CHECKSUM_MISMATCH shows integrity failure guidance', () => {
    const machine = deriveMachine({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime_state: 'error' }],
      runtime: { last_error_code: 'ARTIFACT_CHECKSUM_MISMATCH' },
    })
    render(<OnboardingStateGate machine={machine} />)

    expect(screen.getByTestId('prov-error-title').textContent).toBe('Bundle integrity check failed')
    expect(screen.getByTestId('prov-error-guidance').textContent).toContain('republished')
  })

  it('unknown error code falls back to raw code display', () => {
    const machine = deriveMachine({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime_state: 'error' }],
      runtime: { last_error_code: 'CUSTOM_BACKEND_ERROR' },
    })
    render(<OnboardingStateGate machine={machine} />)

    expect(screen.getByTestId('prov-error-title').textContent).toBe('CUSTOM_BACKEND_ERROR')
  })

  it('resolveFromError output maps to same labels as direct resolveApiError', () => {
    const err = new Error('timeout')
    err.status = 503
    err.data = { error: 'workspace_not_found' }

    const fromError = resolveFromError(err)
    const direct = resolveApiError(503, 'workspace_not_found')

    expect(fromError.label).toBe(direct.label)
    expect(fromError.guidance).toBe(direct.guidance)
  })
})

// =====================================================================
// 3. Workspace switch + navigation
// =====================================================================

describe('Workspace switch integration', () => {
  it('switcher triggers onSwitchWorkspace callback with target ID', () => {
    const onSwitch = vi.fn()
    const workspaces = [
      { id: 'ws1', name: 'Alpha' },
      { id: 'ws2', name: 'Beta' },
    ]
    render(
      <WorkspaceSwitcher
        workspaces={workspaces}
        selectedWorkspaceId="ws1"
        onSwitchWorkspace={onSwitch}
      />,
    )
    fireEvent.click(screen.getByTestId('workspace-switcher-trigger'))
    fireEvent.click(screen.getByTestId('workspace-option-ws2'))

    expect(onSwitch).toHaveBeenCalledWith('ws2')
  })

  it('switching workspace updates derived state independently', () => {
    // Derive state for ws1 (ready) then ws2 (provisioning).
    const ws1 = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [
        { id: 'ws1', runtime_state: 'ready' },
        { id: 'ws2', runtime_state: 'queued' },
      ],
      selectedWorkspaceId: 'ws1',
    })
    const ws2 = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [
        { id: 'ws1', runtime_state: 'ready' },
        { id: 'ws2', runtime_state: 'queued' },
      ],
      selectedWorkspaceId: 'ws2',
    })

    expect(ws1.state).toBe(S.WORKSPACE_SELECTED_READY)
    expect(ws1.selectedWorkspaceId).toBe('ws1')
    expect(ws2.state).toBe(S.WORKSPACE_SELECTED_PROVISIONING)
    expect(ws2.selectedWorkspaceId).toBe('ws2')
  })

  it('switching to non-existent workspace falls back to first workspace', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [
        { id: 'ws1', runtime_state: 'ready' },
        { id: 'ws2', runtime_state: 'queued' },
      ],
      selectedWorkspaceId: 'ws_nonexistent',
    })

    expect(result.selectedWorkspaceId).toBe('ws1')
    expect(result.state).toBe(S.WORKSPACE_SELECTED_READY)
  })
})

// =====================================================================
// 4. Branding resolution through the gate
// =====================================================================

describe('Branding through OnboardingStateGate', () => {
  it('renders branding name from app-config fetch', async () => {
    globalThis.fetch = mockFetch({ name: 'Acme Corp', logo: '/acme.svg' })

    const machine = makeMachine({ state: S.UNAUTHENTICATED })
    render(<OnboardingStateGate machine={machine} />)

    await waitFor(() => {
      expect(screen.getByTestId('onboarding-branding-name').textContent).toBe('Acme Corp')
    })
  })

  it('renders branding logo from app-config fetch', async () => {
    globalThis.fetch = mockFetch({ name: 'Acme Corp', logo: '/acme.svg' })

    const machine = makeMachine({ state: S.UNAUTHENTICATED })
    render(<OnboardingStateGate machine={machine} />)

    await waitFor(() => {
      const logoEl = screen.getByTestId('onboarding-branding-logo')
      expect(logoEl.getAttribute('src')).toBe('/acme.svg')
    })
  })

  it('falls back to local config when app-config fetch fails', async () => {
    globalThis.fetch = vi.fn(() => Promise.reject(new Error('network')))

    const machine = makeMachine({ state: S.UNAUTHENTICATED })
    render(<OnboardingStateGate machine={machine} />)

    await waitFor(() => {
      expect(screen.getByTestId('onboarding-branding-name').textContent).toBe('Boring UI')
    })
  })

  it('workspace branding overrides app-config when passed', async () => {
    globalThis.fetch = mockFetch({ name: 'Acme Corp', logo: '/acme.svg' })

    const machine = makeMachine({ state: S.UNAUTHENTICATED })
    render(
      <OnboardingStateGate
        machine={machine}
        workspaceBranding={{ name: 'Custom WS', logo: '/ws.svg' }}
      />,
    )

    await waitFor(() => {
      expect(screen.getByTestId('onboarding-branding-name').textContent).toBe('Custom WS')
    })
  })
})

// =====================================================================
// 5. Retry recovery flow
// =====================================================================

describe('Retry recovery flow', () => {
  it('retry button in gate calls machine.retryProvisioning', async () => {
    const retryFn = vi.fn(() => Promise.resolve({ ok: true }))
    const machine = deriveMachine(
      {
        user: { id: 'u1' },
        workspaces: [{ id: 'ws1', runtime_state: 'error' }],
        runtime: { last_error_code: 'STEP_TIMEOUT' },
      },
      { retryProvisioning: retryFn },
    )
    render(<OnboardingStateGate machine={machine} />)

    // The embedded ProvisioningError has its own retry.
    await act(async () => {
      fireEvent.click(screen.getByTestId('prov-retry-btn'))
    })

    // The ProvisioningError's onRetry calls machine.retryProvisioning.
    expect(retryFn).toHaveBeenCalledOnce()
  })

  it('state transitions from error → provisioning → ready through events', () => {
    let state = S.WORKSPACE_SELECTED_ERROR

    // User retries → RUNTIME_PROVISIONING event.
    state = advanceOnboardingState(state, E.RUNTIME_PROVISIONING)
    expect(state).toBe(S.WORKSPACE_SELECTED_PROVISIONING)

    // Provisioning completes → RUNTIME_READY event.
    state = advanceOnboardingState(state, E.RUNTIME_READY)
    expect(state).toBe(S.WORKSPACE_SELECTED_READY)
  })

  it('full cycle: derive error → advance to provisioning → advance to ready', () => {
    const errorResult = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime_state: 'error' }],
    })
    expect(errorResult.state).toBe(S.WORKSPACE_SELECTED_ERROR)

    // Re-derive after runtime state changes to provisioning.
    const provResult = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime_state: 'queued' }],
    })
    expect(provResult.state).toBe(S.WORKSPACE_SELECTED_PROVISIONING)

    // Re-derive after runtime becomes ready.
    const readyResult = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime_state: 'ready' }],
    })
    expect(readyResult.state).toBe(S.WORKSPACE_SELECTED_READY)
  })
})

// =====================================================================
// 6. Auth session expiry resets gate
// =====================================================================

describe('Auth session expiry', () => {
  it('401 error on /me resets to unauthenticated regardless of workspace state', () => {
    const result = deriveOnboardingState({
      user: null,
      workspaces: [{ id: 'ws1', runtime_state: 'ready' }],
      errors: { me: { code: '401' } },
    })

    expect(result.state).toBe(S.UNAUTHENTICATED)
    expect(result.selectedWorkspace).toBeNull()
  })

  it('gate shows sign-in after auth expiry', () => {
    const machine = deriveMachine({
      user: null,
      workspaces: [],
      errors: { me: { code: '401' } },
    })
    render(<OnboardingStateGate machine={machine} />)

    expect(screen.getByText('Sign in required')).toBeTruthy()
    expect(screen.getByText('Sign in')).toBeTruthy()
  })

  it('AUTH_REQUIRED from ready resets to unauthenticated', () => {
    const state = advanceOnboardingState(S.WORKSPACE_SELECTED_READY, E.AUTH_REQUIRED)
    expect(state).toBe(S.UNAUTHENTICATED)
  })

  it('AUTH_REQUIRED from provisioning resets to unauthenticated', () => {
    const state = advanceOnboardingState(S.WORKSPACE_SELECTED_PROVISIONING, E.AUTH_REQUIRED)
    expect(state).toBe(S.UNAUTHENTICATED)
  })

  it('AUTH_REQUIRED from error resets to unauthenticated', () => {
    const state = advanceOnboardingState(S.WORKSPACE_SELECTED_ERROR, E.AUTH_REQUIRED)
    expect(state).toBe(S.UNAUTHENTICATED)
  })
})

// =====================================================================
// 7. Cross-workspace isolation in state derivation
// =====================================================================

describe('Cross-workspace isolation', () => {
  it('each workspace runtime state is derived independently', () => {
    const workspaces = [
      { id: 'ws1', runtime_state: 'ready' },
      { id: 'ws2', runtime_state: 'error' },
      { id: 'ws3', runtime_state: 'queued' },
    ]

    const r1 = deriveOnboardingState({ user: { id: 'u1' }, workspaces, selectedWorkspaceId: 'ws1' })
    const r2 = deriveOnboardingState({ user: { id: 'u1' }, workspaces, selectedWorkspaceId: 'ws2' })
    const r3 = deriveOnboardingState({ user: { id: 'u1' }, workspaces, selectedWorkspaceId: 'ws3' })

    expect(r1.state).toBe(S.WORKSPACE_SELECTED_READY)
    expect(r2.state).toBe(S.WORKSPACE_SELECTED_ERROR)
    expect(r3.state).toBe(S.WORKSPACE_SELECTED_PROVISIONING)
  })

  it('gate UI changes based on selected workspace', () => {
    const readyMachine = deriveMachine({
      user: { id: 'u1' },
      workspaces: [
        { id: 'ws1', runtime_state: 'ready' },
        { id: 'ws2', runtime_state: 'error' },
      ],
      selectedWorkspaceId: 'ws1',
    })

    const { unmount } = render(<OnboardingStateGate machine={readyMachine} />)
    expect(screen.getByText('Workspace ready')).toBeTruthy()
    unmount()

    const errorMachine = deriveMachine({
      user: { id: 'u1' },
      workspaces: [
        { id: 'ws1', runtime_state: 'ready' },
        { id: 'ws2', runtime_state: 'error' },
      ],
      selectedWorkspaceId: 'ws2',
    })
    render(<OnboardingStateGate machine={errorMachine} />)
    // "Provisioning failed" may appear in both gate title and error component.
    const gateText = screen.getByTestId('onboarding-gate').textContent
    expect(gateText).toContain('Provisioning failed')
  })
})

// =====================================================================
// 8. Error code mapping through full UX stack
// =====================================================================

describe('Error code mapping through UX stack', () => {
  const ERROR_CODES = [
    { code: 401, label: 'Session expired', action: 'sign_in' },
    { code: 403, label: 'Permission denied', action: 'contact_admin' },
    { code: 404, label: 'Not found', action: 'navigate_back' },
    { code: 409, label: 'Conflict', action: 'refresh' },
    { code: 410, label: 'No longer available', action: 'navigate_back' },
    { code: 429, label: 'Too many requests', action: 'retry' },
    { code: 500, label: 'Server error', action: 'retry' },
    { code: 503, label: 'Service unavailable', action: 'retry' },
  ]

  ERROR_CODES.forEach(({ code, label, action }) => {
    it(`HTTP ${code} resolves to "${label}" with action "${action}"`, () => {
      const info = resolveApiError(code)
      expect(info.label).toBe(label)
      expect(info.action).toBe(action)
    })
  })

  it('backend error codes override generic status labels', () => {
    const info = resolveApiError(409, 'file_already_exists')
    expect(info.label).toBe('File already exists')
    expect(info.action).toBe('rename')
  })

  it('retryable is true only for 5xx and 429', () => {
    expect(resolveApiError(400).retryable).toBe(false)
    expect(resolveApiError(401).retryable).toBe(false)
    expect(resolveApiError(403).retryable).toBe(false)
    expect(resolveApiError(429).retryable).toBe(true)
    expect(resolveApiError(500).retryable).toBe(true)
    expect(resolveApiError(502).retryable).toBe(true)
    expect(resolveApiError(503).retryable).toBe(true)
  })
})

// =====================================================================
// 9. State machine transition completeness
// =====================================================================

describe('State machine transition completeness for gate states', () => {
  const ALL_STATES = Object.values(S)
  const ALL_EVENTS = Object.values(E)

  ALL_STATES.forEach((state) => {
    it(`${state}: AUTH_REQUIRED always leads to unauthenticated`, () => {
      expect(advanceOnboardingState(state, E.AUTH_REQUIRED)).toBe(S.UNAUTHENTICATED)
    })
  })

  it('every state has at least one valid transition', () => {
    ALL_STATES.forEach((state) => {
      const transitions = ALL_EVENTS.filter(
        (event) => advanceOnboardingState(state, event) !== state,
      )
      expect(transitions.length).toBeGreaterThan(0)
    })
  })

  it('no event from UNAUTHENTICATED skips to ready without intermediate states', () => {
    // From UNAUTHENTICATED, no single event should reach READY.
    ALL_EVENTS.forEach((event) => {
      const result = advanceOnboardingState(S.UNAUTHENTICATED, event)
      expect(result).not.toBe(S.WORKSPACE_SELECTED_READY)
      expect(result).not.toBe(S.WORKSPACE_SELECTED_ERROR)
      expect(result).not.toBe(S.WORKSPACE_SELECTED_PROVISIONING)
    })
  })

  it('gate title is defined for all onboarding states', () => {
    ALL_STATES.forEach((state) => {
      const machine = makeMachine({ state })
      const { unmount } = render(<OnboardingStateGate machine={machine} />)
      // Should render without crashing and have a heading.
      expect(screen.getByTestId('onboarding-gate')).toBeTruthy()
      unmount()
    })
  })
})

// =====================================================================
// 10. ProvisioningError embedded in gate with branding
// =====================================================================

describe('ProvisioningError embedded in gate', () => {
  it('error gate shows both branding and error details', async () => {
    globalThis.fetch = mockFetch({ name: 'Acme Corp' })

    const machine = deriveMachine({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', name: 'Prod', runtime_state: 'error' }],
      runtime: { last_error_code: 'STEP_TIMEOUT', last_error_detail: 'Deploy step exceeded limit' },
    })
    render(<OnboardingStateGate machine={machine} />)

    await waitFor(() => {
      expect(screen.getByTestId('onboarding-branding-name').textContent).toBe('Acme Corp')
    })
    expect(screen.getByTestId('prov-error-title').textContent).toBe('Provisioning step timed out')
    expect(screen.getByTestId('prov-error-detail').textContent).toBe('Deploy step exceeded limit')
    expect(screen.getByTestId('prov-error-workspace').textContent).toContain('Prod')
  })

  it('error gate shows workspace name in meta section', () => {
    const machine = deriveMachine({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', name: 'My WS', runtime_state: 'error' }],
    })
    render(<OnboardingStateGate machine={machine} />)

    // Meta section shows workspace and state info.
    const metaTexts = screen.getByTestId('onboarding-gate').textContent
    expect(metaTexts).toContain('Workspace: My WS')
    expect(metaTexts).toContain('State: workspace_selected_error')
  })

  it('error gate hides provisioning error when state is not error', () => {
    const machine = deriveMachine({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime_state: 'ready' }],
    })
    render(<OnboardingStateGate machine={machine} />)

    expect(screen.queryByTestId('provisioning-error')).toBeNull()
  })
})

// =====================================================================
// 11. Loading states
// =====================================================================

describe('Loading states', () => {
  it('provisioning state shows "Refreshing status" when isLoading is true', () => {
    const machine = deriveMachine({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', name: 'Loading WS', runtime_state: 'queued' }],
      loading: true,
    })
    render(<OnboardingStateGate machine={machine} />)

    expect(screen.getByText('Refreshing status…')).toBeTruthy()
  })

  it('provisioning state shows workspace name when not loading', () => {
    const machine = deriveMachine({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', name: 'My WS', runtime_state: 'queued' }],
    })
    render(<OnboardingStateGate machine={machine} />)

    const gateText = screen.getByTestId('onboarding-gate').textContent
    expect(gateText).toContain('Provisioning My WS')
  })

  it('refresh button is always present', () => {
    const machine = makeMachine({ state: S.UNAUTHENTICATED })
    render(<OnboardingStateGate machine={machine} />)

    expect(screen.getByText('Refresh status')).toBeTruthy()
  })

  it('refresh button calls machine.refresh', () => {
    const refreshFn = vi.fn()
    const machine = makeMachine({ state: S.UNAUTHENTICATED, refresh: refreshFn })
    render(<OnboardingStateGate machine={machine} />)

    fireEvent.click(screen.getByText('Refresh status'))
    expect(refreshFn).toHaveBeenCalledOnce()
  })
})

// =====================================================================
// 12. Primary action buttons invoke correct machine methods
// =====================================================================

describe('Primary action buttons', () => {
  it('Sign in button calls startLogin', () => {
    const loginFn = vi.fn()
    const machine = makeMachine({ state: S.UNAUTHENTICATED, startLogin: loginFn })
    render(<OnboardingStateGate machine={machine} />)

    fireEvent.click(screen.getByText('Sign in'))
    expect(loginFn).toHaveBeenCalledOnce()
  })

  it('Create workspace button calls startCreateWorkspace', () => {
    const createFn = vi.fn()
    const machine = makeMachine({
      state: S.AUTHENTICATED_NO_WORKSPACE,
      startCreateWorkspace: createFn,
    })
    render(<OnboardingStateGate machine={machine} />)

    fireEvent.click(screen.getByText('Create workspace'))
    expect(createFn).toHaveBeenCalledOnce()
  })

  it('Open workspace app button calls openWorkspaceApp with ID', () => {
    const openFn = vi.fn()
    const machine = makeMachine({
      state: S.WORKSPACE_SELECTED_READY,
      selectedWorkspaceId: 'ws_target',
      openWorkspaceApp: openFn,
    })
    render(<OnboardingStateGate machine={machine} />)

    fireEvent.click(screen.getByText('Open workspace app'))
    expect(openFn).toHaveBeenCalledWith('ws_target')
  })

  it('Retry provisioning button calls retryProvisioning', () => {
    const retryFn = vi.fn()
    const machine = makeMachine({
      state: S.WORKSPACE_SELECTED_ERROR,
      retryProvisioning: retryFn,
    })
    render(<OnboardingStateGate machine={machine} />)

    // Use the primary action button (not the embedded ProvisioningError retry).
    const primaryBtn = screen.getByText('Retry provisioning', {
      selector: '.onboarding-primary-btn span',
    })
    fireEvent.click(primaryBtn)
    expect(retryFn).toHaveBeenCalledOnce()
  })
})

// =====================================================================
// 13. Workspace switcher + gate coordination
// =====================================================================

describe('Workspace switcher + gate coordination', () => {
  it('switcher shows workspaces from derived state', () => {
    const derived = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [
        { id: 'ws1', name: 'Alpha', runtime_state: 'ready' },
        { id: 'ws2', name: 'Beta', runtime_state: 'queued' },
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
  })

  it('switcher is empty when user has no workspaces', () => {
    const derived = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [],
    })

    const { container } = render(
      <WorkspaceSwitcher
        workspaces={derived.workspaces}
        selectedWorkspaceId={derived.selectedWorkspaceId}
      />,
    )

    expect(container.innerHTML).toBe('')
  })
})

// =====================================================================
// 14. Event trace reflects full derivation path
// =====================================================================

describe('Event trace reflects full derivation path', () => {
  it('unauthenticated trace includes AUTH_REQUIRED only', () => {
    const result = deriveOnboardingState({ user: null, workspaces: [] })
    expect(result.eventTrace).toEqual([E.AUTH_REQUIRED])
  })

  it('authenticated-no-workspace trace includes AUTHENTICATED + NO_WORKSPACE', () => {
    const result = deriveOnboardingState({ user: { id: 'u1' }, workspaces: [] })
    expect(result.eventTrace).toEqual([E.AUTHENTICATED, E.NO_WORKSPACE])
  })

  it('workspace-ready trace includes AUTHENTICATED + WORKSPACE_SELECTED + RUNTIME_READY', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime_state: 'ready' }],
    })
    expect(result.eventTrace).toEqual([E.AUTHENTICATED, E.WORKSPACE_SELECTED, E.RUNTIME_READY])
  })

  it('workspace-error trace includes AUTHENTICATED + WORKSPACE_SELECTED + RUNTIME_ERROR', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime_state: 'error' }],
    })
    expect(result.eventTrace).toEqual([E.AUTHENTICATED, E.WORKSPACE_SELECTED, E.RUNTIME_ERROR])
  })

  it('workspace-provisioning trace includes AUTHENTICATED + WORKSPACE_SELECTED + RUNTIME_PROVISIONING', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime_state: 'queued' }],
    })
    expect(result.eventTrace).toEqual([E.AUTHENTICATED, E.WORKSPACE_SELECTED, E.RUNTIME_PROVISIONING])
  })
})
