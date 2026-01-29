import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Badge from '../../components/primitives/Badge'

describe('Badge', () => {
  describe('variants', () => {
    const variants = ['success', 'warning', 'error', 'info', 'neutral', 'violet']

    variants.forEach((variant) => {
      it(`renders ${variant} variant`, () => {
        render(<Badge variant={variant}>Test</Badge>)
        const badge = screen.getByText('Test')
        expect(badge).toBeInTheDocument()
      })
    })
  })

  describe('sizes', () => {
    it('renders sm size', () => {
      render(<Badge size="sm">Small</Badge>)
      const badge = screen.getByText('Small')
      expect(badge).toHaveClass('px-2', 'py-0.5', 'text-xs')
    })

    it('renders md size (default)', () => {
      render(<Badge>Medium</Badge>)
      const badge = screen.getByText('Medium')
      expect(badge).toHaveClass('px-2.5', 'py-1', 'text-sm')
    })

    it('renders lg size', () => {
      render(<Badge size="lg">Large</Badge>)
      const badge = screen.getByText('Large')
      expect(badge).toHaveClass('px-3', 'py-1.5', 'text-base')
    })
  })

  describe('dismissible', () => {
    it('does not show close button by default', () => {
      render(<Badge>Not dismissible</Badge>)
      const closeButton = screen.queryByLabelText('Dismiss badge')
      expect(closeButton).not.toBeInTheDocument()
    })

    it('shows close button when dismissible is true', () => {
      render(<Badge dismissible>Dismissible</Badge>)
      const closeButton = screen.getByLabelText('Dismiss badge')
      expect(closeButton).toBeInTheDocument()
    })

    it('calls onDismiss when close button is clicked', async () => {
      const handleDismiss = vi.fn()
      render(<Badge dismissible onDismiss={handleDismiss}>Dismissible</Badge>)

      const closeButton = screen.getByLabelText('Dismiss badge')
      await userEvent.click(closeButton)

      expect(handleDismiss).toHaveBeenCalledTimes(1)
    })
  })

  describe('content', () => {
    it('renders text content', () => {
      render(<Badge>Badge Text</Badge>)
      expect(screen.getByText('Badge Text')).toBeInTheDocument()
    })

    it('renders children components', () => {
      render(
        <Badge>
          <span data-testid="child">Child Element</span>
        </Badge>
      )
      expect(screen.getByTestId('child')).toBeInTheDocument()
    })
  })

  describe('custom classes', () => {
    it('accepts custom className', () => {
      render(<Badge className="custom-class">Custom</Badge>)
      const badge = screen.getByText('Custom')
      expect(badge).toHaveClass('custom-class')
    })
  })

  describe('accessibility', () => {
    it('close button is accessible', async () => {
      const handleDismiss = vi.fn()
      render(<Badge dismissible onDismiss={handleDismiss}>Accessible</Badge>)

      const closeButton = screen.getByLabelText('Dismiss badge')
      closeButton.focus()

      expect(closeButton).toHaveFocus()
    })
  })
})
