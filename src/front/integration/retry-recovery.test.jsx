/**
 * End-to-end retry recovery flow integration tests.
 *
 * Bead: bd-223o.14.4.1 (H4a)
 *
 * Validates the full retry recovery cycle with real hook + real components:
 *   1. useOnboardingState hook fetches APIs, derives error state
 *   2. OnboardingStateGate renders ProvisioningError with retry button
 *   3. User clicks retry → POST /retry → hook re-fetches → runtime ready
 *   4. Gate UI updates to workspace_selected_ready
 *   5. Error codes propagate through full stack (hook → gate → ProvisioningError)
 *   6. Retry failure keeps gate in error state with failure message
 *   7. Multiple retry attempts tracked correctly
 *   8. Retry during provisioning shows spinner, then resolves
 *   9. Different error codes produce different guidance text
 *  10. Refresh button reloads state without POST /retry
 */

import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, fireEvent, cleanup, waitFor, act } from '@testing-library/react'
import { renderHook } from '@testing-library/react'

import { ONBOARDING_STATES } from '../onboarding/stateMachine.js'
import OnboardingStateGate from '../components/OnboardingStateGate.jsx'
import { useOnboardingState } from '../hooks/useOnboardingState.js'

const S = ONBOARDING_STATES

// ── Fetch mock helpers ───────────────────────────────────────────────

const jsonResponse = (data, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  text: async () => JSON.stringify(data),
  json: async () => data,
})

const errorResponse = (status, code, message) => ({
  ok: false,
  status,
  text: async () => JSON.stringify({ code, message, detail: message }),
  json: async () => ({ code, message, detail: message }),
})

const ME_RESPONSE = { id: 'u1', email: 'test@example.com', user_id: 'u1' }
const WS_RESPONSE = [{ id: 'ws1', name: 'Test Workspace' }]

const RUNTIME_ERROR = {
  state: 'error',
  last_error_code: 'STEP_TIMEOUT',
  last_error_detail: 'Step health_check exceeded 120s',
  attempt: 2,
}

const RUNTIME_READY = { state: 'ready' }

const RUNTIME_PROVISIONING = { state: 'provisioning' }

/**
 * Build a fetch mock that returns configured responses per URL pattern.
 * Routes are matched in order; first match wins.
 */
const buildFetchMock = (routes) =>
  vi.fn(async (url) => {
    const path = typeof url === 'string' ? url : url.toString()
    for (const [pattern, response] of routes) {
      if (path.includes(pattern)) {
        return typeof response === 'function' ? response() : response
      }
    }
    return errorResponse(404, 'not_found', 'No mock route')
  })

// ── Test setup ───────────────────────────────────────────────────────

let originalFetch

beforeEach(() => {
  originalFetch = globalThis.fetch
})

afterEach(() => {
  globalThis.fetch = originalFetch
  cleanup()
  vi.restoreAllMocks()
})

// =====================================================================
// 1. Full retry recovery: error → retry → ready
// =====================================================================

describe('Full retry recovery cycle', () => {
  it('error state → click retry → POST /retry → reload → ready', async () => {
    let callCount = 0

    globalThis.fetch = buildFetchMock([
      ['/api/v1/me', jsonResponse(ME_RESPONSE)],
      ['/api/v1/workspaces/ws1/retry', jsonResponse({ ok: true }, 200)],
      ['/api/v1/workspaces/ws1/runtime', () => {
        callCount++
        // First call returns error, subsequent calls return ready.
        return callCount <= 1
          ? jsonResponse(RUNTIME_ERROR)
          : jsonResponse(RUNTIME_READY)
      }],
      ['/api/v1/workspaces', jsonResponse(WS_RESPONSE)],
    ])

    const { result } = renderHook(() => useOnboardingState({ enabled: true }))

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    // Should be in error state from first runtime fetch.
    expect(result.current.state).toBe(S.WORKSPACE_SELECTED_ERROR)
    expect(result.current.selectedWorkspaceId).toBe('ws1')

    // Call retryProvisioning (simulates what ProvisioningError does).
    let retryResult
    await act(async () => {
      retryResult = await result.current.retryProvisioning()
    })

    expect(retryResult).toEqual({ ok: true })

    // After retry, loadState re-fetches and runtime is now ready.
    await waitFor(() => {
      expect(result.current.state).toBe(S.WORKSPACE_SELECTED_READY)
    })
  })

  it('error state → retry fails → stays in error with failure reason', async () => {
    globalThis.fetch = buildFetchMock([
      ['/api/v1/me', jsonResponse(ME_RESPONSE)],
      ['/api/v1/workspaces/ws1/retry', errorResponse(429, 'rate_limited', 'Too many retries')],
      ['/api/v1/workspaces/ws1/runtime', jsonResponse(RUNTIME_ERROR)],
      ['/api/v1/workspaces', jsonResponse(WS_RESPONSE)],
    ])

    const { result } = renderHook(() => useOnboardingState({ enabled: true }))

    await waitFor(() => {
      expect(result.current.state).toBe(S.WORKSPACE_SELECTED_ERROR)
    })

    let retryResult
    await act(async () => {
      retryResult = await result.current.retryProvisioning()
    })

    // Retry endpoint failed — retryProvisioning returns { ok: false }.
    expect(retryResult.ok).toBe(false)
    expect(retryResult.reason).toBe('rate_limited')

    // State remains error (loadState re-fetches after retry attempt).
    expect(result.current.state).toBe(S.WORKSPACE_SELECTED_ERROR)
  })

  it('retry succeeds but runtime still provisioning → stays in provisioning', async () => {
    let runtimeCallCount = 0

    globalThis.fetch = buildFetchMock([
      ['/api/v1/me', jsonResponse(ME_RESPONSE)],
      ['/api/v1/workspaces/ws1/retry', jsonResponse({ ok: true })],
      ['/api/v1/workspaces/ws1/runtime', () => {
        runtimeCallCount++
        return runtimeCallCount <= 1
          ? jsonResponse(RUNTIME_ERROR)
          : jsonResponse(RUNTIME_PROVISIONING)
      }],
      ['/api/v1/workspaces', jsonResponse(WS_RESPONSE)],
    ])

    const { result } = renderHook(() => useOnboardingState({ enabled: true }))

    await waitFor(() => {
      expect(result.current.state).toBe(S.WORKSPACE_SELECTED_ERROR)
    })

    await act(async () => {
      await result.current.retryProvisioning()
    })

    // Runtime now returns provisioning instead of ready.
    await waitFor(() => {
      expect(result.current.state).toBe(S.WORKSPACE_SELECTED_PROVISIONING)
    })
  })
})

// =====================================================================
// 2. Gate + hook integration: rendered retry UI
// =====================================================================

describe('Gate renders retry UI from hook state', () => {
  it('gate shows ProvisioningError with error code from hook', async () => {
    globalThis.fetch = buildFetchMock([
      ['/api/v1/me', jsonResponse(ME_RESPONSE)],
      ['/api/v1/workspaces/ws1/runtime', jsonResponse(RUNTIME_ERROR)],
      ['/api/v1/workspaces', jsonResponse(WS_RESPONSE)],
    ])

    const { result } = renderHook(() => useOnboardingState({ enabled: true }))

    await waitFor(() => {
      expect(result.current.state).toBe(S.WORKSPACE_SELECTED_ERROR)
    })

    render(<OnboardingStateGate machine={result.current} />)

    // ProvisioningError should render inside the gate.
    expect(screen.getByTestId('provisioning-error')).toBeTruthy()
    expect(screen.getByTestId('prov-error-title').textContent).toBe(
      'Provisioning step timed out',
    )
    expect(screen.getByTestId('prov-error-code')).toBeTruthy()
    expect(screen.getByTestId('prov-error-detail').textContent).toBe(
      'Step health_check exceeded 120s',
    )
    expect(screen.getByTestId('prov-error-guidance').textContent).toContain(
      'transient infrastructure',
    )
  })

  it('gate shows workspace name from hook state', async () => {
    globalThis.fetch = buildFetchMock([
      ['/api/v1/me', jsonResponse(ME_RESPONSE)],
      ['/api/v1/workspaces/ws1/runtime', jsonResponse(RUNTIME_ERROR)],
      ['/api/v1/workspaces', jsonResponse(WS_RESPONSE)],
    ])

    const { result } = renderHook(() => useOnboardingState({ enabled: true }))

    await waitFor(() => {
      expect(result.current.state).toBe(S.WORKSPACE_SELECTED_ERROR)
    })

    render(<OnboardingStateGate machine={result.current} />)

    expect(screen.getByTestId('prov-error-workspace').textContent).toContain(
      'Test Workspace',
    )
  })

  it('gate shows attempt count > 1 from runtime', async () => {
    globalThis.fetch = buildFetchMock([
      ['/api/v1/me', jsonResponse(ME_RESPONSE)],
      ['/api/v1/workspaces/ws1/runtime', jsonResponse(RUNTIME_ERROR)],
      ['/api/v1/workspaces', jsonResponse(WS_RESPONSE)],
    ])

    const { result } = renderHook(() => useOnboardingState({ enabled: true }))

    await waitFor(() => {
      expect(result.current.state).toBe(S.WORKSPACE_SELECTED_ERROR)
    })

    render(<OnboardingStateGate machine={result.current} />)

    expect(screen.getByTestId('prov-error-attempt').textContent).toContain('2')
  })
})

// =====================================================================
// 3. Error code propagation through full stack
// =====================================================================

describe('Error code propagation', () => {
  const ERROR_CODES = [
    {
      code: 'STEP_TIMEOUT',
      title: 'Provisioning step timed out',
      hasGuidance: true,
    },
    {
      code: 'ARTIFACT_CHECKSUM_MISMATCH',
      title: 'Bundle integrity check failed',
      hasGuidance: true,
    },
    {
      code: 'health_check_failed',
      title: 'Health check failed',
      hasGuidance: true,
    },
    {
      code: 'sandbox_creation_failed',
      title: 'Sandbox creation failed',
      hasGuidance: false,
    },
  ]

  ERROR_CODES.forEach(({ code, title, hasGuidance }) => {
    it(`${code} propagates through hook → gate → ProvisioningError`, async () => {
      const runtimeWithCode = {
        state: 'error',
        last_error_code: code,
        last_error_detail: `Detail for ${code}`,
      }

      globalThis.fetch = buildFetchMock([
        ['/api/v1/me', jsonResponse(ME_RESPONSE)],
        ['/api/v1/workspaces/ws1/runtime', jsonResponse(runtimeWithCode)],
        ['/api/v1/workspaces', jsonResponse(WS_RESPONSE)],
      ])

      const { result } = renderHook(() => useOnboardingState({ enabled: true }))

      await waitFor(() => {
        expect(result.current.state).toBe(S.WORKSPACE_SELECTED_ERROR)
      })

      render(<OnboardingStateGate machine={result.current} />)

      expect(screen.getByTestId('prov-error-title').textContent).toBe(title)

      if (hasGuidance) {
        expect(screen.getByTestId('prov-error-guidance')).toBeTruthy()
      } else {
        expect(screen.queryByTestId('prov-error-guidance')).toBeNull()
      }
    })
  })

  it('runtime error without explicit code falls back to provision_failed', async () => {
    const runtimeNoCode = {
      state: 'error',
      // No last_error_code field.
    }

    globalThis.fetch = buildFetchMock([
      ['/api/v1/me', jsonResponse(ME_RESPONSE)],
      ['/api/v1/workspaces/ws1/runtime', jsonResponse(runtimeNoCode)],
      ['/api/v1/workspaces', jsonResponse(WS_RESPONSE)],
    ])

    const { result } = renderHook(() => useOnboardingState({ enabled: true }))

    await waitFor(() => {
      expect(result.current.state).toBe(S.WORKSPACE_SELECTED_ERROR)
    })

    render(<OnboardingStateGate machine={result.current} />)

    // OnboardingStateGate uses `runtimeErrorCode || 'provision_failed'`.
    expect(screen.getByTestId('prov-error-title').textContent).toBe(
      'Provisioning failed',
    )
  })

  it('runtime fetch failure (500) synthesizes error runtime in hook', async () => {
    globalThis.fetch = buildFetchMock([
      ['/api/v1/me', jsonResponse(ME_RESPONSE)],
      ['/api/v1/workspaces/ws1/runtime', errorResponse(500, 'internal_error', 'Server error')],
      ['/api/v1/workspaces', jsonResponse(WS_RESPONSE)],
    ])

    const { result } = renderHook(() => useOnboardingState({ enabled: true }))

    await waitFor(() => {
      expect(result.current.state).toBe(S.WORKSPACE_SELECTED_ERROR)
    })

    // Hook synthesizes runtime with last_error_code from the caught error.
    expect(result.current.runtime).toBeTruthy()
    expect(result.current.runtime.state).toBe('error')
  })
})

// =====================================================================
// 4. Refresh button vs retry button
// =====================================================================

describe('Refresh vs retry distinction', () => {
  it('refresh reloads state without POST /retry', async () => {
    let runtimeCalls = 0

    globalThis.fetch = buildFetchMock([
      ['/api/v1/me', jsonResponse(ME_RESPONSE)],
      ['/api/v1/workspaces/ws1/retry', () => {
        throw new Error('retry should NOT be called')
      }],
      ['/api/v1/workspaces/ws1/runtime', () => {
        runtimeCalls++
        return runtimeCalls <= 1
          ? jsonResponse(RUNTIME_ERROR)
          : jsonResponse(RUNTIME_READY)
      }],
      ['/api/v1/workspaces', jsonResponse(WS_RESPONSE)],
    ])

    const { result } = renderHook(() => useOnboardingState({ enabled: true }))

    await waitFor(() => {
      expect(result.current.state).toBe(S.WORKSPACE_SELECTED_ERROR)
    })

    // Call refresh (not retryProvisioning).
    await act(async () => {
      await result.current.refresh()
    })

    // Should have re-fetched and found ready runtime.
    await waitFor(() => {
      expect(result.current.state).toBe(S.WORKSPACE_SELECTED_READY)
    })

    // No /retry call was made.
    const retryCalls = globalThis.fetch.mock.calls.filter(
      ([url]) => typeof url === 'string' && url.includes('/retry'),
    )
    expect(retryCalls.length).toBe(0)
  })

  it('retryProvisioning calls POST /retry then reloads state', async () => {
    let runtimeCalls = 0

    globalThis.fetch = buildFetchMock([
      ['/api/v1/me', jsonResponse(ME_RESPONSE)],
      ['/api/v1/workspaces/ws1/retry', jsonResponse({ ok: true })],
      ['/api/v1/workspaces/ws1/runtime', () => {
        runtimeCalls++
        return runtimeCalls <= 1
          ? jsonResponse(RUNTIME_ERROR)
          : jsonResponse(RUNTIME_READY)
      }],
      ['/api/v1/workspaces', jsonResponse(WS_RESPONSE)],
    ])

    const { result } = renderHook(() => useOnboardingState({ enabled: true }))

    await waitFor(() => {
      expect(result.current.state).toBe(S.WORKSPACE_SELECTED_ERROR)
    })

    await act(async () => {
      await result.current.retryProvisioning()
    })

    // Verify /retry was called.
    const retryCalls = globalThis.fetch.mock.calls.filter(
      ([url]) => typeof url === 'string' && url.includes('/retry'),
    )
    expect(retryCalls.length).toBe(1)

    // Verify POST method.
    const [, retryInit] = retryCalls[0]
    expect(retryInit?.method).toBe('POST')

    // State should now be ready.
    await waitFor(() => {
      expect(result.current.state).toBe(S.WORKSPACE_SELECTED_READY)
    })
  })
})

// =====================================================================
// 5. ProvisioningError retry button wiring through gate
// =====================================================================

describe('ProvisioningError retry button in gate', () => {
  it('clicking prov-retry-btn calls retryProvisioning on the machine', async () => {
    const retryFn = vi.fn(() => Promise.resolve({ ok: true }))

    const machine = {
      state: S.WORKSPACE_SELECTED_ERROR,
      eventTrace: [],
      user: ME_RESPONSE,
      workspaces: WS_RESPONSE,
      selectedWorkspace: WS_RESPONSE[0],
      selectedWorkspaceId: 'ws1',
      runtime: RUNTIME_ERROR,
      runtimeState: 'error',
      isLoading: false,
      errors: {},
      errorCode: 'STEP_TIMEOUT',
      enabled: true,
      isBlocking: true,
      refresh: vi.fn(),
      startLogin: vi.fn(),
      startCreateWorkspace: vi.fn(),
      openWorkspaceApp: vi.fn(),
      retryProvisioning: retryFn,
    }

    render(<OnboardingStateGate machine={machine} />)

    // Click the ProvisioningError retry button (not the primary action).
    await act(async () => {
      fireEvent.click(screen.getByTestId('prov-retry-btn'))
    })

    expect(retryFn).toHaveBeenCalledOnce()
  })

  it('prov-retry-btn shows spinner during async retry', async () => {
    let resolveRetry
    const retryFn = vi.fn(
      () => new Promise((r) => { resolveRetry = r }),
    )

    const machine = {
      state: S.WORKSPACE_SELECTED_ERROR,
      eventTrace: [],
      user: ME_RESPONSE,
      workspaces: WS_RESPONSE,
      selectedWorkspace: WS_RESPONSE[0],
      selectedWorkspaceId: 'ws1',
      runtime: RUNTIME_ERROR,
      runtimeState: 'error',
      isLoading: false,
      errors: {},
      errorCode: 'STEP_TIMEOUT',
      enabled: true,
      isBlocking: true,
      refresh: vi.fn(),
      startLogin: vi.fn(),
      startCreateWorkspace: vi.fn(),
      openWorkspaceApp: vi.fn(),
      retryProvisioning: retryFn,
    }

    render(<OnboardingStateGate machine={machine} />)

    // Start retry.
    await act(async () => {
      fireEvent.click(screen.getByTestId('prov-retry-btn'))
    })

    // Button should show "Retrying" and be disabled.
    expect(screen.getByTestId('prov-retry-btn').textContent).toContain('Retrying')
    expect(screen.getByTestId('prov-retry-btn').disabled).toBe(true)

    // Resolve the retry.
    await act(async () => { resolveRetry({ ok: true }) })

    expect(screen.getByTestId('prov-retry-btn').textContent).toContain('Retry provisioning')
    expect(screen.getByTestId('prov-retry-btn').disabled).toBe(false)
  })

  it('prov-retry-btn shows failure message when retry returns { ok: false }', async () => {
    const retryFn = vi.fn(() => Promise.resolve({ ok: false, reason: 'quota_exceeded' }))

    const machine = {
      state: S.WORKSPACE_SELECTED_ERROR,
      eventTrace: [],
      user: ME_RESPONSE,
      workspaces: WS_RESPONSE,
      selectedWorkspace: WS_RESPONSE[0],
      selectedWorkspaceId: 'ws1',
      runtime: RUNTIME_ERROR,
      runtimeState: 'error',
      isLoading: false,
      errors: {},
      errorCode: 'STEP_TIMEOUT',
      enabled: true,
      isBlocking: true,
      refresh: vi.fn(),
      startLogin: vi.fn(),
      startCreateWorkspace: vi.fn(),
      openWorkspaceApp: vi.fn(),
      retryProvisioning: retryFn,
    }

    render(<OnboardingStateGate machine={machine} />)

    await act(async () => {
      fireEvent.click(screen.getByTestId('prov-retry-btn'))
    })

    await waitFor(() => {
      expect(screen.getByTestId('prov-retry-failed').textContent).toContain('quota_exceeded')
    })
  })
})

// =====================================================================
// 6. Multiple sequential retries
// =====================================================================

describe('Multiple sequential retries', () => {
  it('first retry fails, second retry succeeds → reaches ready', async () => {
    let retryCallCount = 0
    let runtimeCallCount = 0

    globalThis.fetch = buildFetchMock([
      ['/api/v1/me', jsonResponse(ME_RESPONSE)],
      ['/api/v1/workspaces/ws1/retry', () => {
        retryCallCount++
        if (retryCallCount === 1) {
          return errorResponse(500, 'internal_error', 'Retry infra issue')
        }
        return jsonResponse({ ok: true })
      }],
      ['/api/v1/workspaces/ws1/runtime', () => {
        runtimeCallCount++
        // First two calls: error (initial + after failed retry reload).
        // Third call: ready (after successful retry reload).
        return runtimeCallCount <= 2
          ? jsonResponse(RUNTIME_ERROR)
          : jsonResponse(RUNTIME_READY)
      }],
      ['/api/v1/workspaces', jsonResponse(WS_RESPONSE)],
    ])

    const { result } = renderHook(() => useOnboardingState({ enabled: true }))

    await waitFor(() => {
      expect(result.current.state).toBe(S.WORKSPACE_SELECTED_ERROR)
    })

    // First retry fails.
    let r1
    await act(async () => {
      r1 = await result.current.retryProvisioning()
    })
    expect(r1.ok).toBe(false)
    expect(result.current.state).toBe(S.WORKSPACE_SELECTED_ERROR)

    // Second retry succeeds.
    let r2
    await act(async () => {
      r2 = await result.current.retryProvisioning()
    })
    expect(r2.ok).toBe(true)

    await waitFor(() => {
      expect(result.current.state).toBe(S.WORKSPACE_SELECTED_READY)
    })
  })
})

// =====================================================================
// 7. Retry with no workspace selected
// =====================================================================

describe('Retry edge cases', () => {
  it('retryProvisioning returns missing_workspace_id when no workspace', async () => {
    globalThis.fetch = buildFetchMock([
      ['/api/v1/me', jsonResponse(ME_RESPONSE)],
      ['/api/v1/workspaces', jsonResponse([])],
    ])

    const { result } = renderHook(() => useOnboardingState({ enabled: true }))

    await waitFor(() => {
      expect(result.current.state).toBe(S.AUTHENTICATED_NO_WORKSPACE)
    })

    let retryResult
    await act(async () => {
      retryResult = await result.current.retryProvisioning()
    })

    expect(retryResult).toEqual({ ok: false, reason: 'missing_workspace_id' })
  })

  it('hook disabled → retryProvisioning returns missing_workspace_id', async () => {
    const { result } = renderHook(() => useOnboardingState({ enabled: false }))

    // When disabled, machine is pass-through with no selectedWorkspaceId.
    let retryResult
    await act(async () => {
      retryResult = await result.current.retryProvisioning()
    })

    expect(retryResult).toEqual({ ok: false, reason: 'missing_workspace_id' })
  })
})

// =====================================================================
// 8. isBlocking reflects error state
// =====================================================================

describe('isBlocking during error and recovery', () => {
  it('isBlocking is true in error state', async () => {
    globalThis.fetch = buildFetchMock([
      ['/api/v1/me', jsonResponse(ME_RESPONSE)],
      ['/api/v1/workspaces/ws1/runtime', jsonResponse(RUNTIME_ERROR)],
      ['/api/v1/workspaces', jsonResponse(WS_RESPONSE)],
    ])

    const { result } = renderHook(() => useOnboardingState({ enabled: true }))

    await waitFor(() => {
      expect(result.current.state).toBe(S.WORKSPACE_SELECTED_ERROR)
    })

    expect(result.current.isBlocking).toBe(true)
  })

  it('isBlocking becomes false after retry recovers to ready', async () => {
    let runtimeCalls = 0

    globalThis.fetch = buildFetchMock([
      ['/api/v1/me', jsonResponse(ME_RESPONSE)],
      ['/api/v1/workspaces/ws1/retry', jsonResponse({ ok: true })],
      ['/api/v1/workspaces/ws1/runtime', () => {
        runtimeCalls++
        return runtimeCalls <= 1
          ? jsonResponse(RUNTIME_ERROR)
          : jsonResponse(RUNTIME_READY)
      }],
      ['/api/v1/workspaces', jsonResponse(WS_RESPONSE)],
    ])

    const { result } = renderHook(() => useOnboardingState({ enabled: true }))

    await waitFor(() => {
      expect(result.current.isBlocking).toBe(true)
    })

    await act(async () => {
      await result.current.retryProvisioning()
    })

    await waitFor(() => {
      expect(result.current.isBlocking).toBe(false)
      expect(result.current.state).toBe(S.WORKSPACE_SELECTED_READY)
    })
  })
})

// =====================================================================
// 9. Gate state text updates after recovery
// =====================================================================

describe('Gate text updates reflect state transitions', () => {
  it('gate title changes from "Provisioning failed" to "Workspace ready"', () => {
    const errorMachine = {
      state: S.WORKSPACE_SELECTED_ERROR,
      eventTrace: [],
      user: ME_RESPONSE,
      workspaces: WS_RESPONSE,
      selectedWorkspace: WS_RESPONSE[0],
      selectedWorkspaceId: 'ws1',
      runtime: RUNTIME_ERROR,
      runtimeState: 'error',
      isLoading: false,
      errors: {},
      errorCode: 'STEP_TIMEOUT',
      enabled: true,
      isBlocking: true,
      refresh: vi.fn(),
      startLogin: vi.fn(),
      startCreateWorkspace: vi.fn(),
      openWorkspaceApp: vi.fn(),
      retryProvisioning: vi.fn(),
    }

    const { unmount } = render(<OnboardingStateGate machine={errorMachine} />)
    const gateText = screen.getByTestId('onboarding-gate').textContent
    expect(gateText).toContain('Provisioning failed')
    unmount()

    const readyMachine = {
      ...errorMachine,
      state: S.WORKSPACE_SELECTED_READY,
      runtime: RUNTIME_READY,
      runtimeState: 'ready',
      errorCode: '',
      isBlocking: false,
    }

    render(<OnboardingStateGate machine={readyMachine} />)
    const readyText = screen.getByTestId('onboarding-gate').textContent
    expect(readyText).toContain('Workspace ready')
    expect(readyText).not.toContain('Provisioning failed')
  })

  it('ProvisioningError is not rendered when state is ready', () => {
    const readyMachine = {
      state: S.WORKSPACE_SELECTED_READY,
      eventTrace: [],
      user: ME_RESPONSE,
      workspaces: WS_RESPONSE,
      selectedWorkspace: WS_RESPONSE[0],
      selectedWorkspaceId: 'ws1',
      runtime: RUNTIME_READY,
      runtimeState: 'ready',
      isLoading: false,
      errors: {},
      errorCode: '',
      enabled: true,
      isBlocking: false,
      refresh: vi.fn(),
      startLogin: vi.fn(),
      startCreateWorkspace: vi.fn(),
      openWorkspaceApp: vi.fn(),
      retryProvisioning: vi.fn(),
    }

    render(<OnboardingStateGate machine={readyMachine} />)
    expect(screen.queryByTestId('provisioning-error')).toBeNull()
    expect(screen.queryByTestId('prov-retry-btn')).toBeNull()
  })
})
