/**
 * ApiErrorBanner component unit tests.
 *
 * Bead: bd-223o.14.3.1 (H3a)
 *
 * Validates:
 *   - Renders label and guidance from error info.
 *   - Renders detail when present.
 *   - Does not render when error is null.
 *   - Shows retry button for retryable errors.
 *   - Hides retry button for non-retryable errors.
 *   - Calls onRetry when retry clicked.
 *   - Shows spinner during retry.
 *   - Shows action button when onAction provided and not retryable.
 *   - Calls onAction with action type.
 *   - Shows dismiss button when onDismiss provided.
 *   - Calls onDismiss when dismiss clicked.
 *   - Sets data-status attribute.
 */

import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup, waitFor, act } from '@testing-library/react'
import ApiErrorBanner from './ApiErrorBanner.jsx'

afterEach(cleanup)

const make503 = () => ({
  status: 503,
  label: 'Service unavailable',
  guidance: 'The service is temporarily unavailable.',
  retryable: true,
  action: 'retry',
})

const make403 = () => ({
  status: 403,
  label: 'Permission denied',
  guidance: 'You do not have permission.',
  retryable: false,
  action: 'contact_admin',
})

const make409 = (detail) => ({
  status: 409,
  label: 'File already exists',
  guidance: 'Choose a different name.',
  detail,
  retryable: false,
  action: 'rename',
})

// =====================================================================
// Rendering
// =====================================================================

describe('ApiErrorBanner — rendering', () => {
  it('renders label and guidance', () => {
    render(<ApiErrorBanner error={make503()} />)
    expect(screen.getByTestId('api-error-label').textContent).toBe('Service unavailable')
    expect(screen.getByTestId('api-error-guidance').textContent).toBe(
      'The service is temporarily unavailable.',
    )
  })

  it('renders detail when present', () => {
    render(<ApiErrorBanner error={make409('File foo.txt exists')} />)
    expect(screen.getByTestId('api-error-detail').textContent).toBe('File foo.txt exists')
  })

  it('hides detail when not present', () => {
    render(<ApiErrorBanner error={make503()} />)
    expect(screen.queryByTestId('api-error-detail')).toBeNull()
  })

  it('does not render when error is null', () => {
    const { container } = render(<ApiErrorBanner error={null} />)
    expect(container.innerHTML).toBe('')
  })

  it('sets data-status attribute', () => {
    render(<ApiErrorBanner error={make503()} />)
    expect(screen.getByTestId('api-error-banner').getAttribute('data-status')).toBe('503')
  })
})

// =====================================================================
// Retry
// =====================================================================

describe('ApiErrorBanner — retry', () => {
  it('shows retry button for retryable errors', () => {
    const onRetry = vi.fn()
    render(<ApiErrorBanner error={make503()} onRetry={onRetry} />)
    expect(screen.getByTestId('api-error-retry')).toBeTruthy()
  })

  it('hides retry button for non-retryable errors', () => {
    render(<ApiErrorBanner error={make403()} />)
    expect(screen.queryByTestId('api-error-retry')).toBeNull()
  })

  it('hides retry button when no onRetry callback', () => {
    render(<ApiErrorBanner error={make503()} />)
    expect(screen.queryByTestId('api-error-retry')).toBeNull()
  })

  it('calls onRetry when clicked', async () => {
    const onRetry = vi.fn(() => Promise.resolve())
    render(<ApiErrorBanner error={make503()} onRetry={onRetry} />)
    await act(async () => {
      fireEvent.click(screen.getByTestId('api-error-retry'))
    })
    expect(onRetry).toHaveBeenCalledOnce()
  })

  it('shows "Retrying…" during retry', async () => {
    let resolve
    const onRetry = vi.fn(() => new Promise((r) => { resolve = r }))
    render(<ApiErrorBanner error={make503()} onRetry={onRetry} />)

    await act(async () => {
      fireEvent.click(screen.getByTestId('api-error-retry'))
    })
    expect(screen.getByTestId('api-error-retry').textContent).toContain('Retrying')

    await act(async () => { resolve() })
    expect(screen.getByTestId('api-error-retry').textContent).toContain('Retry')
    expect(screen.getByTestId('api-error-retry').textContent).not.toContain('Retrying')
  })

  it('disables retry button during retry', async () => {
    let resolve
    const onRetry = vi.fn(() => new Promise((r) => { resolve = r }))
    render(<ApiErrorBanner error={make503()} onRetry={onRetry} />)

    await act(async () => {
      fireEvent.click(screen.getByTestId('api-error-retry'))
    })
    expect(screen.getByTestId('api-error-retry').disabled).toBe(true)

    await act(async () => { resolve() })
    expect(screen.getByTestId('api-error-retry').disabled).toBe(false)
  })
})

// =====================================================================
// Action button
// =====================================================================

describe('ApiErrorBanner — action', () => {
  it('shows action button when onAction provided and not retryable', () => {
    const onAction = vi.fn()
    render(<ApiErrorBanner error={make403()} onAction={onAction} />)
    expect(screen.getByTestId('api-error-action')).toBeTruthy()
    expect(screen.getByTestId('api-error-action').textContent).toContain('Contact admin')
  })

  it('calls onAction with action type', () => {
    const onAction = vi.fn()
    render(<ApiErrorBanner error={make403()} onAction={onAction} />)
    fireEvent.click(screen.getByTestId('api-error-action'))
    expect(onAction).toHaveBeenCalledWith('contact_admin')
  })

  it('prefers retry over action when retryable', () => {
    const onRetry = vi.fn(() => Promise.resolve())
    const onAction = vi.fn()
    render(<ApiErrorBanner error={make503()} onRetry={onRetry} onAction={onAction} />)
    expect(screen.getByTestId('api-error-retry')).toBeTruthy()
    expect(screen.queryByTestId('api-error-action')).toBeNull()
  })
})

// =====================================================================
// Dismiss
// =====================================================================

describe('ApiErrorBanner — dismiss', () => {
  it('shows dismiss button when onDismiss provided', () => {
    const onDismiss = vi.fn()
    render(<ApiErrorBanner error={make503()} onDismiss={onDismiss} />)
    expect(screen.getByTestId('api-error-dismiss')).toBeTruthy()
  })

  it('hides dismiss button when no onDismiss', () => {
    render(<ApiErrorBanner error={make503()} />)
    expect(screen.queryByTestId('api-error-dismiss')).toBeNull()
  })

  it('calls onDismiss when clicked', () => {
    const onDismiss = vi.fn()
    render(<ApiErrorBanner error={make503()} onDismiss={onDismiss} />)
    fireEvent.click(screen.getByTestId('api-error-dismiss'))
    expect(onDismiss).toHaveBeenCalledOnce()
  })
})
