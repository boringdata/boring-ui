/**
 * ProvisioningError component unit tests.
 *
 * Bead: bd-223o.14.4 (H4)
 *
 * Validates:
 *   - Renders error title from known error codes.
 *   - Renders raw error code for unknown codes.
 *   - Renders error detail when provided.
 *   - Renders guidance text for codes with guidance.
 *   - Does not render guidance for codes without guidance.
 *   - Renders workspace name when provided.
 *   - Shows attempt count when > 1.
 *   - Hides attempt count when 1 or undefined.
 *   - Retry button fires onRetry callback.
 *   - Shows spinner during retry.
 *   - Shows retry-failed message when onRetry rejects.
 *   - Shows retry-failed message when onRetry returns { ok: false }.
 *   - Retry button disabled during retry.
 */

import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup, waitFor, act } from '@testing-library/react'
import ProvisioningError from './ProvisioningError.jsx'

afterEach(cleanup)

// =====================================================================
// Render — error info
// =====================================================================

describe('ProvisioningError — rendering', () => {
  it('renders known error code label', () => {
    render(<ProvisioningError errorCode="STEP_TIMEOUT" />)
    expect(screen.getByTestId('prov-error-title').textContent).toBe(
      'Provisioning step timed out',
    )
  })

  it('renders raw code when unknown', () => {
    render(<ProvisioningError errorCode="CUSTOM_THING" />)
    expect(screen.getByTestId('prov-error-title').textContent).toBe('CUSTOM_THING')
  })

  it('renders "Unknown error" when no code', () => {
    render(<ProvisioningError />)
    expect(screen.getByTestId('prov-error-title').textContent).toBe('Unknown error')
  })

  it('shows error code badge', () => {
    render(<ProvisioningError errorCode="STEP_TIMEOUT" />)
    const codeEl = screen.getByTestId('prov-error-code')
    expect(codeEl.textContent).toContain('STEP_TIMEOUT')
  })

  it('hides code badge when no errorCode', () => {
    render(<ProvisioningError />)
    expect(screen.queryByTestId('prov-error-code')).toBeNull()
  })

  it('renders error detail', () => {
    render(<ProvisioningError errorCode="STEP_TIMEOUT" errorDetail="Step X exceeded 120s" />)
    expect(screen.getByTestId('prov-error-detail').textContent).toBe('Step X exceeded 120s')
  })

  it('hides detail when not provided', () => {
    render(<ProvisioningError errorCode="STEP_TIMEOUT" />)
    expect(screen.queryByTestId('prov-error-detail')).toBeNull()
  })

  it('renders guidance for STEP_TIMEOUT', () => {
    render(<ProvisioningError errorCode="STEP_TIMEOUT" />)
    const guidance = screen.getByTestId('prov-error-guidance')
    expect(guidance.textContent).toContain('transient infrastructure')
  })

  it('hides guidance for codes without guidance', () => {
    render(<ProvisioningError errorCode="provision_failed" />)
    expect(screen.queryByTestId('prov-error-guidance')).toBeNull()
  })

  it('shows workspace name', () => {
    render(<ProvisioningError errorCode="STEP_TIMEOUT" workspaceName="my-ws" />)
    expect(screen.getByTestId('prov-error-workspace').textContent).toContain('my-ws')
  })

  it('hides workspace when not provided', () => {
    render(<ProvisioningError errorCode="STEP_TIMEOUT" />)
    expect(screen.queryByTestId('prov-error-workspace')).toBeNull()
  })

  it('shows attempt count when > 1', () => {
    render(<ProvisioningError errorCode="STEP_TIMEOUT" attempt={3} />)
    expect(screen.getByTestId('prov-error-attempt').textContent).toContain('3')
  })

  it('hides attempt count when 1', () => {
    render(<ProvisioningError errorCode="STEP_TIMEOUT" attempt={1} />)
    expect(screen.queryByTestId('prov-error-attempt')).toBeNull()
  })

  it('hides attempt count when undefined', () => {
    render(<ProvisioningError errorCode="STEP_TIMEOUT" />)
    expect(screen.queryByTestId('prov-error-attempt')).toBeNull()
  })
})

// =====================================================================
// Retry behaviour
// =====================================================================

describe('ProvisioningError — retry', () => {
  it('calls onRetry when retry button clicked', async () => {
    const onRetry = vi.fn(() => Promise.resolve({ ok: true }))
    render(<ProvisioningError errorCode="STEP_TIMEOUT" onRetry={onRetry} />)
    await act(async () => {
      fireEvent.click(screen.getByTestId('prov-retry-btn'))
    })
    expect(onRetry).toHaveBeenCalledOnce()
  })

  it('shows "Retrying…" text during retry', async () => {
    let resolve
    const onRetry = vi.fn(() => new Promise((r) => { resolve = r }))
    render(<ProvisioningError errorCode="STEP_TIMEOUT" onRetry={onRetry} />)

    await act(async () => {
      fireEvent.click(screen.getByTestId('prov-retry-btn'))
    })
    expect(screen.getByTestId('prov-retry-btn').textContent).toContain('Retrying')

    await act(async () => { resolve({ ok: true }) })
    expect(screen.getByTestId('prov-retry-btn').textContent).toContain('Retry provisioning')
  })

  it('disables button during retry', async () => {
    let resolve
    const onRetry = vi.fn(() => new Promise((r) => { resolve = r }))
    render(<ProvisioningError errorCode="STEP_TIMEOUT" onRetry={onRetry} />)

    await act(async () => {
      fireEvent.click(screen.getByTestId('prov-retry-btn'))
    })
    expect(screen.getByTestId('prov-retry-btn').disabled).toBe(true)

    await act(async () => { resolve({ ok: true }) })
    expect(screen.getByTestId('prov-retry-btn').disabled).toBe(false)
  })

  it('shows retry-failed when onRetry returns { ok: false }', async () => {
    const onRetry = vi.fn(() => Promise.resolve({ ok: false, reason: 'quota_exceeded' }))
    render(<ProvisioningError errorCode="STEP_TIMEOUT" onRetry={onRetry} />)

    await act(async () => {
      fireEvent.click(screen.getByTestId('prov-retry-btn'))
    })

    await waitFor(() => {
      expect(screen.getByTestId('prov-retry-failed').textContent).toContain('quota_exceeded')
    })
  })

  it('shows retry-failed when onRetry throws', async () => {
    const onRetry = vi.fn(() => Promise.reject(new Error('network')))
    render(<ProvisioningError errorCode="STEP_TIMEOUT" onRetry={onRetry} />)

    await act(async () => {
      fireEvent.click(screen.getByTestId('prov-retry-btn'))
    })

    await waitFor(() => {
      expect(screen.getByTestId('prov-retry-failed').textContent).toContain('retry_exception')
    })
  })
})
