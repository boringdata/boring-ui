import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Button from '../../components/primitives/Button'

describe('Button', () => {
  describe('variants', () => {
    it('renders primary variant', () => {
      render(<Button variant="primary">Primary</Button>)
      const button = screen.getByText('Primary')
      expect(button).toHaveClass('bg-accent')
    })

    it('renders secondary variant', () => {
      render(<Button variant="secondary">Secondary</Button>)
      const button = screen.getByText('Secondary')
      expect(button).toHaveClass('bg-bg-secondary')
    })

    it('renders ghost variant', () => {
      render(<Button variant="ghost">Ghost</Button>)
      const button = screen.getByText('Ghost')
      expect(button).toHaveClass('text-text-primary')
    })

    it('renders outline variant', () => {
      render(<Button variant="outline">Outline</Button>)
      const button = screen.getByText('Outline')
      expect(button).toHaveClass('border-2', 'border-accent')
    })

    it('renders danger variant', () => {
      render(<Button variant="danger">Danger</Button>)
      const button = screen.getByText('Danger')
      expect(button).toHaveClass('bg-error')
    })
  })

  describe('sizes', () => {
    it('renders xs size', () => {
      render(<Button size="xs">XS</Button>)
      const button = screen.getByText('XS')
      expect(button).toHaveClass('px-2', 'py-1', 'text-xs')
    })

    it('renders md size (default)', () => {
      render(<Button>Medium</Button>)
      const button = screen.getByText('Medium')
      expect(button).toHaveClass('px-4', 'py-2', 'text-base')
    })

    it('renders xl size', () => {
      render(<Button size="xl">XL</Button>)
      const button = screen.getByText('XL')
      expect(button).toHaveClass('px-6', 'py-3', 'text-xl')
    })
  })

  describe('states', () => {
    it('disables button when disabled prop is true', () => {
      render(<Button disabled>Disabled</Button>)
      const button = screen.getByText('Disabled')
      expect(button).toBeDisabled()
      expect(button).toHaveClass('disabled:opacity-50')
    })

    it('shows loading spinner when loading is true', () => {
      render(<Button loading>Loading</Button>)
      const button = screen.getByText('Loading')
      expect(button).toHaveAttribute('aria-busy', 'true')
      expect(button).toBeDisabled()
    })

    it('disables button when loading is true', () => {
      render(<Button loading>Loading</Button>)
      const button = screen.getByText('Loading')
      expect(button).toBeDisabled()
    })
  })

  describe('interactions', () => {
    it('calls onClick when clicked', async () => {
      const handleClick = vi.fn()
      render(<Button onClick={handleClick}>Click me</Button>)

      const button = screen.getByText('Click me')
      await userEvent.click(button)

      expect(handleClick).toHaveBeenCalledTimes(1)
    })

    it('does not call onClick when disabled', async () => {
      const handleClick = vi.fn()
      render(<Button disabled onClick={handleClick}>Disabled</Button>)

      const button = screen.getByText('Disabled')
      await userEvent.click(button)

      expect(handleClick).not.toHaveBeenCalled()
    })

    it('does not call onClick when loading', async () => {
      const handleClick = vi.fn()
      render(<Button loading onClick={handleClick}>Loading</Button>)

      const button = screen.getByText('Loading')
      await userEvent.click(button)

      expect(handleClick).not.toHaveBeenCalled()
    })
  })

  describe('icons', () => {
    it('renders icon before text by default', () => {
      const Icon = () => <span data-testid="test-icon">★</span>
      render(<Button icon={<Icon />}>With Icon</Button>)

      const icon = screen.getByTestId('test-icon')
      const button = screen.getByText('With Icon')

      expect(icon.parentElement).toEqual(button)
      expect(icon.className).toContain('mr-2')
    })

    it('renders icon after text when iconRight is true', () => {
      const Icon = () => <span data-testid="test-icon">★</span>
      render(<Button icon={<Icon />} iconRight>With Icon</Button>)

      const icon = screen.getByTestId('test-icon')
      expect(icon.className).toContain('ml-2')
    })

    it('renders icon without margin when no children', () => {
      const Icon = () => <span data-testid="test-icon">★</span>
      render(<Button icon={<Icon />} />)

      const icon = screen.getByTestId('test-icon')
      expect(icon.className).not.toContain('mr-2')
    })
  })

  describe('accessibility', () => {
    it('is keyboard accessible', async () => {
      const handleClick = vi.fn()
      render(<Button onClick={handleClick}>Keyboard</Button>)

      const button = screen.getByText('Keyboard')
      button.focus()

      expect(button).toHaveFocus()
    })

    it('has focus visible ring', () => {
      render(<Button>Focus Ring</Button>)
      const button = screen.getByText('Focus Ring')
      expect(button).toHaveClass('focus-visible:ring-2')
    })

    it('sets aria-busy when loading', () => {
      render(<Button loading>Loading</Button>)
      const button = screen.getByText('Loading')
      expect(button).toHaveAttribute('aria-busy', 'true')
    })
  })

  describe('custom classes', () => {
    it('accepts custom className', () => {
      render(<Button className="custom-class">Custom</Button>)
      const button = screen.getByText('Custom')
      expect(button).toHaveClass('custom-class')
    })
  })
})
