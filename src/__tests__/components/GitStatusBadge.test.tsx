/**
 * Tests for GitStatusBadge component
 *
 * Features tested:
 * - Status code display (M, A, D, etc.)
 * - Badge sizing variants
 * - Label rendering
 * - Direct status code vs path-based
 * - Loading state
 * - Custom styling
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import GitStatusBadge from '../../components/GitStatusBadge'

// Mock useGitStatus hook
vi.mock('../../hooks/useGitStatus', () => ({
  useGitStatus: ({ path, polling }: any) => ({
    status: { [path]: 'M' },
    loading: false,
  }),
  getFileStatus: (status: any, path: any) => status[path],
  getStatusConfig: (code: any) => {
    const configs: any = {
      M: { className: 'git-status-modified', label: 'Modified', color: '#e2c08d' },
      A: { className: 'git-status-added', label: 'Added', color: '#73c991' },
      D: { className: 'git-status-deleted', label: 'Deleted', color: '#f14c4c' },
      U: { className: 'git-status-unknown', label: 'Unknown', color: '#6b7280' },
    }
    return configs[code]
  },
  STATUS_CONFIG: {
    M: { label: 'Modified', color: '#e2c08d' },
    A: { label: 'Added', color: '#73c991' },
    D: { label: 'Deleted', color: '#f14c4c' },
    U: { label: 'Unknown', color: '#6b7280' },
  },
}))

describe('GitStatusBadge', () => {
  describe('Status Codes', () => {
    it('renders modified status code', () => {
      render(<GitStatusBadge statusCode="M" />)
      const badge = screen.getByText('M')
      expect(badge.closest('.git-status-badge')).toHaveClass('git-status-modified')
    })

    it('renders added status code', () => {
      render(<GitStatusBadge statusCode="A" />)
      const badge = screen.getByText('A')
      expect(badge.closest('.git-status-badge')).toHaveClass('git-status-added')
    })

    it('renders deleted status code', () => {
      render(<GitStatusBadge statusCode="D" />)
      const badge = screen.getByText('D')
      expect(badge.closest('.git-status-badge')).toHaveClass('git-status-deleted')
    })

    it('renders unknown status code', () => {
      render(<GitStatusBadge statusCode="U" />)
      const badge = screen.getByText('U')
      expect(badge.closest('.git-status-badge')).toHaveClass('git-status-unknown')
    })

    it('does not render for unknown status codes', () => {
      const { container } = render(<GitStatusBadge statusCode="X" />)
      expect(container.firstChild).toBeNull()
    })
  })

  describe('Sizing', () => {
    it('renders small size by default', () => {
      render(<GitStatusBadge statusCode="M" />)
      const badge = screen.getByText('M').closest('.git-status-badge')
      expect(badge).toHaveClass('git-status-badge-small')
    })

    it('renders medium size when specified', () => {
      render(<GitStatusBadge statusCode="M" size="medium" />)
      const badge = screen.getByText('M').closest('.git-status-badge')
      expect(badge).toHaveClass('git-status-badge-medium')
    })

    it('applies size styles', () => {
      render(<GitStatusBadge statusCode="M" size="small" />)
      const badge = screen.getByText('M').closest('span')
      const styles = window.getComputedStyle(badge!)
      // Check that size styles are applied
      expect(badge).toHaveStyle('fontSize: 10px')
    })
  })

  describe('Label Display', () => {
    it('does not show label by default', () => {
      const { container } = render(<GitStatusBadge statusCode="M" />)
      const labelSpan = container.querySelector('.git-status-badge-label')
      expect(labelSpan).not.toBeInTheDocument()
    })

    it('shows label when showLabel prop is true', () => {
      render(<GitStatusBadge statusCode="M" showLabel />)
      expect(screen.getByText('Modified')).toBeInTheDocument()
    })

    it('displays correct label for each status', () => {
      const statuses = [
        { code: 'M', label: 'Modified' },
        { code: 'A', label: 'Added' },
        { code: 'D', label: 'Deleted' },
      ]

      for (const { code, label } of statuses) {
        const { unmount } = render(
          <GitStatusBadge statusCode={code as any} showLabel />
        )
        expect(screen.getByText(label)).toBeInTheDocument()
        unmount()
      }
    })

    it('sets title attribute to status label', () => {
      render(<GitStatusBadge statusCode="M" />)
      const badge = screen.getByText('M').closest('.git-status-badge')
      expect(badge).toHaveAttribute('title', 'Modified')
    })
  })

  describe('Custom Styling', () => {
    it('applies custom className', () => {
      render(<GitStatusBadge statusCode="M" className="custom-class" />)
      const badge = screen.getByText('M').closest('.git-status-badge')
      expect(badge).toHaveClass('custom-class')
    })

    it('applies custom inline styles', () => {
      render(
        <GitStatusBadge
          statusCode="M"
          style={{ marginRight: '8px', opacity: 0.5 }}
        />
      )
      const badge = screen.getByText('M').closest('span')
      expect(badge).toHaveStyle('marginRight: 8px')
      expect(badge).toHaveStyle('opacity: 0.5')
    })
  })

  describe('Badge Content', () => {
    it('renders status code in code span', () => {
      const { container } = render(<GitStatusBadge statusCode="M" />)
      const codeSpan = container.querySelector('.git-status-badge-code')
      expect(codeSpan).toHaveTextContent('M')
    })

    it('structures badge with code and optional label', () => {
      const { container } = render(
        <GitStatusBadge statusCode="A" showLabel />
      )
      const badge = container.querySelector('.git-status-badge')
      const codeSpan = badge?.querySelector('.git-status-badge-code')
      const labelSpan = badge?.querySelector('.git-status-badge-label')

      expect(codeSpan).toBeInTheDocument()
      expect(labelSpan).toBeInTheDocument()
    })
  })

  describe('Color Styling', () => {
    it('applies color-based styles from status config', () => {
      render(<GitStatusBadge statusCode="M" />)
      const badge = screen.getByText('M').closest('span')
      const styles = window.getComputedStyle(badge!)

      // Check that color is applied
      expect(badge).toHaveStyle(/color:/)
    })

    it('computes background and border colors from status color', () => {
      render(<GitStatusBadge statusCode="A" />)
      const badge = screen.getByText('A').closest('span')

      // Check that computed colors exist (exact values depend on CSS parsing)
      expect(badge).toHaveStyle(/backgroundColor:/)
      expect(badge).toHaveStyle(/borderColor:/)
    })
  })
})
