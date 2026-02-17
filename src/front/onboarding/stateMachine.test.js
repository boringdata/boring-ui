/**
 * Onboarding state-machine unit tests.
 *
 * Bead: bd-223o.14.1.1 (H1a)
 *
 * Validates deterministic state transitions and fallback behavior:
 *   - advanceOnboardingState transition table completeness
 *   - deriveOnboardingState for all auth/workspace/runtime snapshots
 *   - Unknown events leave state unchanged
 *   - AUTH_REQUIRED always resets to unauthenticated from any state
 *   - Runtime state normalization (queued → provisioning, etc.)
 *   - Workspace selection with preferred ID
 *   - Error code propagation through derived state
 *   - Event trace reflects the derivation path
 */

import { describe, it, expect } from 'vitest'
import {
  ONBOARDING_STATES,
  ONBOARDING_EVENTS,
  advanceOnboardingState,
  deriveOnboardingState,
} from './stateMachine.js'

const S = ONBOARDING_STATES
const E = ONBOARDING_EVENTS

// =====================================================================
// 1. advanceOnboardingState — transition table
// =====================================================================

describe('advanceOnboardingState', () => {
  it('transitions from unauthenticated to authenticated_no_workspace on AUTHENTICATED', () => {
    expect(advanceOnboardingState(S.UNAUTHENTICATED, E.AUTHENTICATED)).toBe(
      S.AUTHENTICATED_NO_WORKSPACE,
    )
  })

  it('stays unauthenticated on AUTH_REQUIRED from unauthenticated', () => {
    expect(advanceOnboardingState(S.UNAUTHENTICATED, E.AUTH_REQUIRED)).toBe(
      S.UNAUTHENTICATED,
    )
  })

  it('transitions from authenticated_no_workspace to provisioning on WORKSPACE_SELECTED', () => {
    expect(
      advanceOnboardingState(S.AUTHENTICATED_NO_WORKSPACE, E.WORKSPACE_SELECTED),
    ).toBe(S.WORKSPACE_SELECTED_PROVISIONING)
  })

  it('resets to unauthenticated on AUTH_REQUIRED from authenticated_no_workspace', () => {
    expect(
      advanceOnboardingState(S.AUTHENTICATED_NO_WORKSPACE, E.AUTH_REQUIRED),
    ).toBe(S.UNAUTHENTICATED)
  })

  it('transitions from provisioning to ready on RUNTIME_READY', () => {
    expect(
      advanceOnboardingState(S.WORKSPACE_SELECTED_PROVISIONING, E.RUNTIME_READY),
    ).toBe(S.WORKSPACE_SELECTED_READY)
  })

  it('transitions from provisioning to error on RUNTIME_ERROR', () => {
    expect(
      advanceOnboardingState(S.WORKSPACE_SELECTED_PROVISIONING, E.RUNTIME_ERROR),
    ).toBe(S.WORKSPACE_SELECTED_ERROR)
  })

  it('transitions from ready back to provisioning on WORKSPACE_SELECTED', () => {
    expect(
      advanceOnboardingState(S.WORKSPACE_SELECTED_READY, E.WORKSPACE_SELECTED),
    ).toBe(S.WORKSPACE_SELECTED_PROVISIONING)
  })

  it('transitions from error back to provisioning on RUNTIME_PROVISIONING', () => {
    expect(
      advanceOnboardingState(S.WORKSPACE_SELECTED_ERROR, E.RUNTIME_PROVISIONING),
    ).toBe(S.WORKSPACE_SELECTED_PROVISIONING)
  })

  it('transitions from error to ready on RUNTIME_READY', () => {
    expect(
      advanceOnboardingState(S.WORKSPACE_SELECTED_ERROR, E.RUNTIME_READY),
    ).toBe(S.WORKSPACE_SELECTED_READY)
  })

  // AUTH_REQUIRED from every state leads to unauthenticated.
  const allStates = Object.values(S)
  allStates.forEach((state) => {
    it(`AUTH_REQUIRED from ${state} → unauthenticated`, () => {
      expect(advanceOnboardingState(state, E.AUTH_REQUIRED)).toBe(
        S.UNAUTHENTICATED,
      )
    })
  })

  it('unknown event leaves state unchanged', () => {
    expect(advanceOnboardingState(S.WORKSPACE_SELECTED_READY, 'UNKNOWN')).toBe(
      S.WORKSPACE_SELECTED_READY,
    )
  })

  it('unknown state returns current state', () => {
    expect(advanceOnboardingState('nonexistent_state', E.AUTHENTICATED)).toBe(
      'nonexistent_state',
    )
  })
})

// =====================================================================
// 2. deriveOnboardingState — unauthenticated
// =====================================================================

describe('deriveOnboardingState — unauthenticated', () => {
  it('returns unauthenticated when user is null', () => {
    const result = deriveOnboardingState({ user: null, workspaces: [] })
    expect(result.state).toBe(S.UNAUTHENTICATED)
    expect(result.user).toBeNull()
  })

  it('returns unauthenticated when user is undefined', () => {
    const result = deriveOnboardingState({ workspaces: [] })
    expect(result.state).toBe(S.UNAUTHENTICATED)
  })

  it('returns unauthenticated on 401 error', () => {
    const result = deriveOnboardingState({
      user: null,
      workspaces: [],
      errors: { me: { code: '401' } },
    })
    expect(result.state).toBe(S.UNAUTHENTICATED)
    expect(result.errorCode).toBe('401')
  })

  it('returns unauthenticated on "unauthorized" error code', () => {
    const result = deriveOnboardingState({
      user: null,
      workspaces: [],
      errors: { me: { code: 'unauthorized' } },
    })
    expect(result.state).toBe(S.UNAUTHENTICATED)
  })

  it('event trace includes AUTH_REQUIRED', () => {
    const result = deriveOnboardingState({ user: null, workspaces: [] })
    expect(result.eventTrace).toContain(E.AUTH_REQUIRED)
  })
})

// =====================================================================
// 3. deriveOnboardingState — authenticated no workspace
// =====================================================================

describe('deriveOnboardingState — authenticated no workspace', () => {
  it('returns authenticated_no_workspace when workspaces is empty', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [],
    })
    expect(result.state).toBe(S.AUTHENTICATED_NO_WORKSPACE)
  })

  it('returns authenticated_no_workspace when workspaces is null', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: null,
    })
    expect(result.state).toBe(S.AUTHENTICATED_NO_WORKSPACE)
  })

  it('preserves user in result', () => {
    const user = { id: 'u1', email: 'test@x.com' }
    const result = deriveOnboardingState({ user, workspaces: [] })
    expect(result.user).toBe(user)
  })

  it('event trace includes AUTHENTICATED and NO_WORKSPACE', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [],
    })
    expect(result.eventTrace).toContain(E.AUTHENTICATED)
    expect(result.eventTrace).toContain(E.NO_WORKSPACE)
  })
})

// =====================================================================
// 4. deriveOnboardingState — workspace provisioning
// =====================================================================

describe('deriveOnboardingState — provisioning', () => {
  it('returns provisioning when runtime state is "queued"', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime_state: 'queued' }],
    })
    expect(result.state).toBe(S.WORKSPACE_SELECTED_PROVISIONING)
  })

  it('returns provisioning for "creating_sandbox"', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime_state: 'creating_sandbox' }],
    })
    expect(result.state).toBe(S.WORKSPACE_SELECTED_PROVISIONING)
  })

  it('returns provisioning for "bootstrapping"', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime_state: 'bootstrapping' }],
    })
    expect(result.state).toBe(S.WORKSPACE_SELECTED_PROVISIONING)
  })

  it('returns provisioning for "health_check"', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime_state: 'health_check' }],
    })
    expect(result.state).toBe(S.WORKSPACE_SELECTED_PROVISIONING)
  })

  it('returns provisioning for "retrying"', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime_state: 'retrying' }],
    })
    expect(result.state).toBe(S.WORKSPACE_SELECTED_PROVISIONING)
  })

  it('returns provisioning for unknown runtime state', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime_state: 'unknown_state' }],
    })
    expect(result.state).toBe(S.WORKSPACE_SELECTED_PROVISIONING)
  })

  it('returns provisioning when runtime state is empty', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1' }],
    })
    expect(result.state).toBe(S.WORKSPACE_SELECTED_PROVISIONING)
  })

  it('event trace includes WORKSPACE_SELECTED and RUNTIME_PROVISIONING', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime_state: 'queued' }],
    })
    expect(result.eventTrace).toContain(E.WORKSPACE_SELECTED)
    expect(result.eventTrace).toContain(E.RUNTIME_PROVISIONING)
  })
})

// =====================================================================
// 5. deriveOnboardingState — workspace ready
// =====================================================================

describe('deriveOnboardingState — ready', () => {
  it('returns ready when runtime state is "ready"', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime_state: 'ready' }],
    })
    expect(result.state).toBe(S.WORKSPACE_SELECTED_READY)
  })

  it('ready state is case-insensitive', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime_state: 'Ready' }],
    })
    expect(result.state).toBe(S.WORKSPACE_SELECTED_READY)
  })

  it('populates selectedWorkspace and selectedWorkspaceId', () => {
    const ws = { id: 'ws1', runtime_state: 'ready' }
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [ws],
    })
    expect(result.selectedWorkspace).toBe(ws)
    expect(result.selectedWorkspaceId).toBe('ws1')
  })

  it('event trace includes RUNTIME_READY', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime_state: 'ready' }],
    })
    expect(result.eventTrace).toContain(E.RUNTIME_READY)
  })
})

// =====================================================================
// 6. deriveOnboardingState — workspace error
// =====================================================================

describe('deriveOnboardingState — error', () => {
  it('returns error when runtime state is "error"', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime_state: 'error' }],
    })
    expect(result.state).toBe(S.WORKSPACE_SELECTED_ERROR)
  })

  it('returns error when runtime state is "failed"', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime_state: 'failed' }],
    })
    expect(result.state).toBe(S.WORKSPACE_SELECTED_ERROR)
  })

  it('error state is case-insensitive', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime_state: 'Error' }],
    })
    expect(result.state).toBe(S.WORKSPACE_SELECTED_ERROR)
  })

  it('event trace includes RUNTIME_ERROR', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime_state: 'error' }],
    })
    expect(result.eventTrace).toContain(E.RUNTIME_ERROR)
  })
})

// =====================================================================
// 7. Workspace selection logic
// =====================================================================

describe('workspace selection', () => {
  it('selects preferred workspace by id', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [
        { id: 'ws1', runtime_state: 'ready' },
        { id: 'ws2', runtime_state: 'ready' },
      ],
      selectedWorkspaceId: 'ws2',
    })
    expect(result.selectedWorkspaceId).toBe('ws2')
  })

  it('falls back to first workspace if preferred not found', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [
        { id: 'ws1', runtime_state: 'ready' },
        { id: 'ws2', runtime_state: 'ready' },
      ],
      selectedWorkspaceId: 'ws_nonexistent',
    })
    expect(result.selectedWorkspaceId).toBe('ws1')
  })

  it('uses first workspace when no preferred ID', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime_state: 'ready' }],
    })
    expect(result.selectedWorkspaceId).toBe('ws1')
  })

  it('supports workspace_id field alias', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ workspace_id: 'ws1', runtime_state: 'ready' }],
    })
    expect(result.selectedWorkspaceId).toBe('ws1')
  })

  it('supports workspaceId field alias', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ workspaceId: 'ws1', runtime_state: 'ready' }],
    })
    expect(result.selectedWorkspaceId).toBe('ws1')
  })
})

// =====================================================================
// 8. Runtime state extraction from nested shapes
// =====================================================================

describe('runtime state extraction', () => {
  it('reads from runtime argument', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1' }],
      runtime: { runtime_state: 'ready' },
    })
    expect(result.state).toBe(S.WORKSPACE_SELECTED_READY)
  })

  it('reads from runtime.state', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1' }],
      runtime: { state: 'ready' },
    })
    expect(result.state).toBe(S.WORKSPACE_SELECTED_READY)
  })

  it('reads from workspace.runtime.state', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime: { state: 'ready' } }],
    })
    expect(result.state).toBe(S.WORKSPACE_SELECTED_READY)
  })

  it('reads from workspace.runtime.runtime_state', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime: { runtime_state: 'error' } }],
    })
    expect(result.state).toBe(S.WORKSPACE_SELECTED_ERROR)
  })
})

// =====================================================================
// 9. Error code propagation
// =====================================================================

describe('error code propagation', () => {
  it('propagates me error code for unauthenticated', () => {
    const result = deriveOnboardingState({
      user: null,
      errors: { me: { code: '401' } },
    })
    expect(result.errorCode).toBe('401')
  })

  it('propagates workspace error code for no-workspace state', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [],
      errors: { workspaces: { code: '500' } },
    })
    expect(result.errorCode).toBe('500')
  })

  it('propagates runtime error code for error state', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime_state: 'error' }],
      errors: { runtime: { code: 'provision_failed' } },
    })
    expect(result.errorCode).toBe('provision_failed')
  })

  it('errorCode is empty string when no errors', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [{ id: 'ws1', runtime_state: 'ready' }],
    })
    expect(result.errorCode).toBe('')
  })
})

// =====================================================================
// 10. Loading state propagation
// =====================================================================

describe('loading state', () => {
  it('defaults to false when loading not specified', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [],
    })
    expect(result.isLoading).toBe(false)
  })

  it('propagates loading=true', () => {
    const result = deriveOnboardingState({
      user: { id: 'u1' },
      workspaces: [],
      loading: true,
    })
    expect(result.isLoading).toBe(true)
  })
})

// =====================================================================
// 11. ONBOARDING_STATES and ONBOARDING_EVENTS are frozen
// =====================================================================

describe('constants are frozen', () => {
  it('ONBOARDING_STATES is frozen', () => {
    expect(Object.isFrozen(ONBOARDING_STATES)).toBe(true)
  })

  it('ONBOARDING_EVENTS is frozen', () => {
    expect(Object.isFrozen(ONBOARDING_EVENTS)).toBe(true)
  })

  it('all 5 states exist', () => {
    expect(Object.keys(ONBOARDING_STATES)).toHaveLength(5)
  })

  it('all 7 events exist', () => {
    expect(Object.keys(ONBOARDING_EVENTS)).toHaveLength(7)
  })
})
