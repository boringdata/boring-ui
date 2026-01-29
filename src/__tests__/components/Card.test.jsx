import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Card from '../../components/primitives/Card'

describe('Card', () => {
  describe('elevation', () => {
    it('renders with no elevation', () => {
      render(<Card elevation="none">No Elevation</Card>)
      const card = screen.getByText('No Elevation')
      expect(card).toHaveClass('border')
    })

    it('renders with sm elevation', () => {
      render(<Card elevation="sm">Small Shadow</Card>)
      const card = screen.getByText('Small Shadow')
      expect(card).toHaveClass('shadow-sm')
    })

    it('renders with md elevation (default)', () => {
      render(<Card>Medium Shadow</Card>)
      const card = screen.getByText('Medium Shadow')
      expect(card).toHaveClass('shadow-md')
    })

    it('renders with lg elevation', () => {
      render(<Card elevation="lg">Large Shadow</Card>)
      const card = screen.getByText('Large Shadow')
      expect(card).toHaveClass('shadow-lg')
    })

    it('renders with xl elevation', () => {
      render(<Card elevation="xl">Extra Large Shadow</Card>)
      const card = screen.getByText('Extra Large Shadow')
      expect(card).toHaveClass('shadow-xl')
    })
  })

  describe('padding', () => {
    it('renders with no padding', () => {
      render(<Card padding="none">No Padding</Card>)
      const card = screen.getByText('No Padding')
      expect(card).toHaveClass('p-0')
    })

    it('renders with sm padding', () => {
      render(<Card padding="sm">Small Padding</Card>)
      const card = screen.getByText('Small Padding')
      expect(card).toHaveClass('p-3')
    })

    it('renders with md padding (default)', () => {
      render(<Card>Medium Padding</Card>)
      const card = screen.getByText('Medium Padding')
      expect(card).toHaveClass('p-4')
    })

    it('renders with lg padding', () => {
      render(<Card padding="lg">Large Padding</Card>)
      const card = screen.getByText('Large Padding')
      expect(card).toHaveClass('p-6')
    })

    it('renders with xl padding', () => {
      render(<Card padding="xl">Extra Large Padding</Card>)
      const card = screen.getByText('Extra Large Padding')
      expect(card).toHaveClass('p-8')
    })
  })

  describe('interactive', () => {
    it('does not have hover effects by default', () => {
      render(<Card>Not Interactive</Card>)
      const card = screen.getByText('Not Interactive')
      expect(card).not.toHaveClass('cursor-pointer')
    })

    it('adds hover effects when interactive is true', () => {
      render(<Card interactive>Interactive</Card>)
      const card = screen.getByText('Interactive')
      expect(card).toHaveClass('cursor-pointer', 'hover:shadow-lg')
    })

    it('is clickable when interactive', async () => {
      const handleClick = vi.fn()
      render(<Card interactive onClick={handleClick}>Click me</Card>)

      const card = screen.getByText('Click me')
      await userEvent.click(card)

      expect(handleClick).toHaveBeenCalledTimes(1)
    })
  })

  describe('composable sections', () => {
    it('renders CardHeader', () => {
      render(
        <Card>
          <Card.Header>Header</Card.Header>
        </Card>
      )
      expect(screen.getByText('Header')).toBeInTheDocument()
    })

    it('renders CardBody', () => {
      render(
        <Card>
          <Card.Body>Body</Card.Body>
        </Card>
      )
      expect(screen.getByText('Body')).toBeInTheDocument()
    })

    it('renders CardFooter', () => {
      render(
        <Card>
          <Card.Footer>Footer</Card.Footer>
        </Card>
      )
      expect(screen.getByText('Footer')).toBeInTheDocument()
    })

    it('renders all sections together', () => {
      render(
        <Card>
          <Card.Header>Header Content</Card.Header>
          <Card.Body>Body Content</Card.Body>
          <Card.Footer>Footer Content</Card.Footer>
        </Card>
      )
      expect(screen.getByText('Header Content')).toBeInTheDocument()
      expect(screen.getByText('Body Content')).toBeInTheDocument()
      expect(screen.getByText('Footer Content')).toBeInTheDocument()
    })

    it('CardHeader has border-bottom', () => {
      const { container } = render(
        <Card>
          <Card.Header>Header</Card.Header>
        </Card>
      )
      const header = screen.getByText('Header').parentElement
      expect(header).toHaveClass('border-b')
    })

    it('CardFooter has border-top', () => {
      const { container } = render(
        <Card>
          <Card.Footer>Footer</Card.Footer>
        </Card>
      )
      const footer = screen.getByText('Footer').parentElement
      expect(footer).toHaveClass('border-t')
    })
  })

  describe('custom classes', () => {
    it('accepts custom className', () => {
      render(<Card className="custom-card">Custom</Card>)
      const card = screen.getByText('Custom')
      expect(card).toHaveClass('custom-card')
    })
  })

  describe('dark mode', () => {
    it('applies dark mode styles', () => {
      render(<Card>Dark Mode</Card>)
      const card = screen.getByText('Dark Mode')
      expect(card).toHaveClass('bg-bg-primary')
    })
  })
})

// Import vi at the top if not already imported
import { vi } from 'vitest'
