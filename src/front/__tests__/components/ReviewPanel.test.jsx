import React from 'react'
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'

import ReviewPanel from '../../shared/panels/ReviewPanel'

vi.mock('../../shared/components/ApprovalPanel', () => ({
  default: ({ request, onFeedbackChange }) => (
    <div data-testid="approval-panel-stub">
      <textarea
        data-testid="feedback-input"
        onChange={(e) => onFeedbackChange?.(e.target.value)}
      />
    </div>
  ),
}))

const makeRequest = (overrides = {}) => ({
  id: 'req-001',
  tool_name: 'write_file',
  description: 'Write to output.txt',
  session_provider: 'pi',
  session_name: 'session-1',
  session_id: 'abcdef1234567890',
  ...overrides,
})

describe('ReviewPanel', () => {
  it('renders panel-content and review-panel-content classes', () => {
    const { container } = render(
      <ReviewPanel params={{ request: makeRequest() }} />,
    )
    expect(
      container.querySelector('.panel-content.review-panel-content'),
    ).toBeInTheDocument()
  })

  it('shows "Review no longer pending" when no request', () => {
    render(<ReviewPanel params={{}} />)
    expect(screen.getByText('Review no longer pending')).toBeInTheDocument()
  })

  it('shows tool name in title', () => {
    render(<ReviewPanel params={{ request: makeRequest() }} />)
    expect(screen.getByText('Review: write_file')).toBeInTheDocument()
  })

  it('shows session metadata', () => {
    render(<ReviewPanel params={{ request: makeRequest() }} />)
    expect(screen.getByText('pi | session-1 | abcdef12')).toBeInTheDocument()
  })

  it('shows file path when provided', () => {
    render(
      <ReviewPanel
        params={{ request: makeRequest(), filePath: 'src/output.txt' }}
      />,
    )
    expect(screen.getByText('src/output.txt')).toBeInTheDocument()
  })

  it('shows "Open file" button when filePath and onOpenFile provided', () => {
    const onOpenFile = vi.fn()
    render(
      <ReviewPanel
        params={{
          request: makeRequest(),
          filePath: 'src/output.txt',
          onOpenFile,
        }}
      />,
    )
    fireEvent.click(screen.getByText('Open file'))
    expect(onOpenFile).toHaveBeenCalledWith('src/output.txt')
  })

  it('calls onDecision with allow when Allow clicked', () => {
    const onDecision = vi.fn()
    render(
      <ReviewPanel
        params={{ request: makeRequest(), onDecision }}
      />,
    )
    fireEvent.click(screen.getByText('Allow'))
    expect(onDecision).toHaveBeenCalledWith('req-001', 'allow', '')
  })

  it('calls onDecision with deny when Deny clicked', () => {
    const onDecision = vi.fn()
    render(
      <ReviewPanel
        params={{ request: makeRequest(), onDecision }}
      />,
    )
    fireEvent.click(screen.getByText('Deny'))
    expect(onDecision).toHaveBeenCalledWith('req-001', 'deny', '')
  })

  it('renders ApprovalPanel component', () => {
    render(<ReviewPanel params={{ request: makeRequest() }} />)
    expect(screen.getByTestId('approval-panel-stub')).toBeInTheDocument()
  })
})
