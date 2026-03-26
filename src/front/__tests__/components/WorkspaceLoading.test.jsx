import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import WorkspaceLoading from '../../components/WorkspaceLoading'

describe('WorkspaceLoading', () => {
  it('renders loading state with title and message', () => {
    render(<WorkspaceLoading title="Opening workspace" message="Connecting to backend services..." />)

    const status = screen.getByRole('status')
    expect(status).toHaveClass('workspace-loading')
    expect(status).toHaveAttribute('aria-live', 'polite')
    expect(screen.getByText('Opening workspace')).toBeInTheDocument()
    expect(screen.getByText('Connecting to backend services...')).toBeInTheDocument()
  })

  it('renders brand logo', () => {
    render(<WorkspaceLoading logo="B" />)
    expect(screen.getByText('B')).toHaveClass('workspace-loading-brand')
  })
})
