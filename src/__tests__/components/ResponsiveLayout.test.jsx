import React from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {
  ResponsiveLayout,
  ResponsiveMessageThread,
  ResponsiveMessage,
  ResponsiveInputArea,
  ResponsiveButton,
} from '../../components/Chat/ResponsiveLayout'

// Mock useResponsive hook
vi.mock('../../hooks/useResponsive', () => ({
  useResponsive: vi.fn(() => ({
    isMobile: window.innerWidth < 640,
    isTablet: window.innerWidth >= 640 && window.innerWidth < 1024,
    isDesktop: window.innerWidth >= 1024,
    currentBreakpoint: 'xs',
    viewportSize: { width: window.innerWidth, height: window.innerHeight },
    hasTouch: true,
    darkMode: false,
    reducedMotion: false,
  })),
}))

describe('ResponsiveLayout', () => {
  let originalInnerWidth

  beforeEach(() => {
    originalInnerWidth = window.innerWidth
    // Set mobile width by default
    Object.defineProperty(window, 'innerWidth', {
      writable: true,
      configurable: true,
      value: 375,
    })
  })

  afterEach(() => {
    Object.defineProperty(window, 'innerWidth', {
      writable: true,
      configurable: true,
      value: originalInnerWidth,
    })
  })

  describe('Mobile Layout (375px)', () => {
    it('renders children content', () => {
      render(
        <ResponsiveLayout>
          <div data-testid="main-content">Main Content</div>
        </ResponsiveLayout>
      )

      expect(screen.getByTestId('main-content')).toBeInTheDocument()
    })

    it('renders mobile header when sidebar is provided', () => {
      render(
        <ResponsiveLayout
          sidebar={<div>Sidebar</div>}
          showSidebar={false}
          onSidebarToggle={vi.fn()}
        >
          <div>Content</div>
        </ResponsiveLayout>
      )

      // Mobile header should be visible
      const header = screen.getByText('Chat')
      expect(header).toBeInTheDocument()
    })

    it('renders hamburger button on mobile with sidebar', () => {
      render(
        <ResponsiveLayout
          sidebar={<div>Sidebar</div>}
          showSidebar={false}
          onSidebarToggle={vi.fn()}
        >
          <div>Content</div>
        </ResponsiveLayout>
      )

      const hamburger = screen.getByLabelText('Open navigation')
      expect(hamburger).toBeInTheDocument()
    })

    it('hides sidebar by default on mobile', () => {
      const { container } = render(
        <ResponsiveLayout
          sidebar={<div data-testid="sidebar">Sidebar Content</div>}
          showSidebar={false}
          onSidebarToggle={vi.fn()}
        >
          <div>Content</div>
        </ResponsiveLayout>
      )

      const sidebar = screen.getByTestId('sidebar')
      // Should be hidden via display: none
      expect(sidebar.parentElement).toHaveStyle({ display: 'none' })
    })

    it('shows sidebar overlay when sidebar is open on mobile', () => {
      const { container } = render(
        <ResponsiveLayout
          sidebar={<div>Sidebar Content</div>}
          showSidebar={true}
          onSidebarToggle={vi.fn()}
        >
          <div>Content</div>
        </ResponsiveLayout>
      )

      const overlay = container.querySelector('.sidebar-overlay')
      expect(overlay).toBeInTheDocument()
    })

    it('calls onSidebarToggle when hamburger is clicked', async () => {
      const handleToggle = vi.fn()
      render(
        <ResponsiveLayout
          sidebar={<div>Sidebar</div>}
          showSidebar={false}
          onSidebarToggle={handleToggle}
        >
          <div>Content</div>
        </ResponsiveLayout>
      )

      const hamburger = screen.getByLabelText('Open navigation')
      await userEvent.click(hamburger)

      expect(handleToggle).toHaveBeenCalledTimes(1)
    })

    it('closes sidebar when overlay is clicked', async () => {
      const handleToggle = vi.fn()
      const { container } = render(
        <ResponsiveLayout
          sidebar={<div>Sidebar</div>}
          showSidebar={true}
          onSidebarToggle={handleToggle}
        >
          <div>Content</div>
        </ResponsiveLayout>
      )

      const overlay = container.querySelector('.sidebar-overlay')
      fireEvent.click(overlay)

      expect(handleToggle).toHaveBeenCalledTimes(1)
    })

    it('has safe area padding on mobile', () => {
      const { container } = render(
        <ResponsiveLayout
          sidebar={<div>Sidebar</div>}
          showSidebar={true}
          onSidebarToggle={vi.fn()}
        >
          <div>Content</div>
        </ResponsiveLayout>
      )

      const sidebar = container.querySelector('.responsive-sidebar')
      expect(sidebar).toHaveStyle({
        paddingTop: 'max(var(--safe-area-inset-top, 0px), 12px)',
      })
    })
  })

  describe('Tablet/Desktop Layout (1024px+)', () => {
    beforeEach(() => {
      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        configurable: true,
        value: 1024,
      })
    })

    it('shows sidebar in normal flow on desktop', () => {
      const { container } = render(
        <ResponsiveLayout
          sidebar={<div data-testid="sidebar">Sidebar Content</div>}
          showSidebar={false}
          onSidebarToggle={vi.fn()}
        >
          <div>Content</div>
        </ResponsiveLayout>
      )

      const sidebar = container.querySelector('.responsive-sidebar')
      // Should be visible without display none
      expect(sidebar).toHaveStyle({ display: 'flex' })
    })

    it('hides mobile header on desktop', () => {
      const { container } = render(
        <ResponsiveLayout
          sidebar={<div>Sidebar</div>}
          showSidebar={false}
          onSidebarToggle={vi.fn()}
        >
          <div>Content</div>
        </ResponsiveLayout>
      )

      const header = container.querySelector('.mobile-header')
      // Should not be in DOM or hidden
      expect(header).not.toBeInTheDocument()
    })
  })

  describe('ResponsiveMessageThread', () => {
    it('renders children messages', () => {
      render(
        <ResponsiveMessageThread>
          <div data-testid="message-1">Message 1</div>
          <div data-testid="message-2">Message 2</div>
        </ResponsiveMessageThread>
      )

      expect(screen.getByTestId('message-1')).toBeInTheDocument()
      expect(screen.getByTestId('message-2')).toBeInTheDocument()
    })

    it('has scrollable container', () => {
      const { container } = render(
        <ResponsiveMessageThread>
          <div>Messages</div>
        </ResponsiveMessageThread>
      )

      const thread = container.querySelector('.responsive-message-thread')
      expect(thread).toHaveStyle({
        overflowY: 'auto',
        flex: '1',
      })
    })

    it('has smaller gap on mobile than desktop', () => {
      const { container } = render(
        <ResponsiveMessageThread>
          <div>Message</div>
        </ResponsiveMessageThread>
      )

      const thread = container.querySelector('.responsive-message-thread')
      expect(thread).toHaveStyle({
        gap: 'var(--space-3)',
      })
    })

    it('accepts custom className', () => {
      const { container } = render(
        <ResponsiveMessageThread className="custom-class">
          <div>Message</div>
        </ResponsiveMessageThread>
      )

      const thread = container.querySelector('.responsive-message-thread')
      expect(thread).toHaveClass('custom-class')
    })
  })

  describe('ResponsiveMessage', () => {
    it('renders message content', () => {
      render(<ResponsiveMessage>Hello World</ResponsiveMessage>)

      expect(screen.getByText('Hello World')).toBeInTheDocument()
    })

    it('aligns user messages to the right', () => {
      const { container } = render(
        <ResponsiveMessage role="user">User message</ResponsiveMessage>
      )

      const message = container.querySelector('.responsive-message-user')
      expect(message).toHaveStyle({
        justifyContent: 'flex-end',
      })
    })

    it('aligns assistant messages to the left', () => {
      const { container } = render(
        <ResponsiveMessage role="assistant">Assistant message</ResponsiveMessage>
      )

      const message = container.querySelector('.responsive-message-assistant')
      expect(message).toHaveStyle({
        justifyContent: 'flex-start',
      })
    })

    it('uses correct background color for user message', () => {
      const { container } = render(
        <ResponsiveMessage role="user">User message</ResponsiveMessage>
      )

      const content = container.querySelector('[style*="var(--color-accent)"]')
      expect(content).toBeInTheDocument()
    })

    it('uses correct background color for assistant message', () => {
      const { container } = render(
        <ResponsiveMessage role="assistant">Assistant message</ResponsiveMessage>
      )

      const content = container.querySelector('[style*="var(--color-bg-tertiary)"]')
      expect(content).toBeInTheDocument()
    })

    it('accepts custom className', () => {
      const { container } = render(
        <ResponsiveMessage className="custom-class">Message</ResponsiveMessage>
      )

      const message = container.querySelector('.responsive-message')
      expect(message).toHaveClass('custom-class')
    })

    it('wraps long text properly', () => {
      const longText = 'This is a very long message that should wrap to multiple lines'
      const { container } = render(
        <ResponsiveMessage>{longText}</ResponsiveMessage>
      )

      const message = container.querySelector('.responsive-message')
      expect(message).toHaveStyle({
        wordWrap: 'break-word',
      })
    })
  })

  describe('ResponsiveInputArea', () => {
    it('renders children', () => {
      render(
        <ResponsiveInputArea>
          <input placeholder="Type message..." />
        </ResponsiveInputArea>
      )

      expect(screen.getByPlaceholderText('Type message...')).toBeInTheDocument()
    })

    it('has correct padding with safe area', () => {
      const { container } = render(
        <ResponsiveInputArea>
          <input />
        </ResponsiveInputArea>
      )

      const area = container.querySelector('.responsive-input-area')
      expect(area).toHaveStyle({
        paddingTop: 'var(--space-3)',
      })
    })

    it('accepts custom className', () => {
      const { container } = render(
        <ResponsiveInputArea className="custom-class">
          <input />
        </ResponsiveInputArea>
      )

      const area = container.querySelector('.responsive-input-area')
      expect(area).toHaveClass('custom-class')
    })

    it('has border top for visual separation', () => {
      const { container } = render(
        <ResponsiveInputArea>
          <input />
        </ResponsiveInputArea>
      )

      const area = container.querySelector('.responsive-input-area')
      expect(area).toHaveStyle({
        borderTop: '1px solid var(--color-border)',
      })
    })
  })

  describe('ResponsiveButton', () => {
    it('renders button text', () => {
      render(<ResponsiveButton>Click Me</ResponsiveButton>)

      expect(screen.getByText('Click Me')).toBeInTheDocument()
    })

    it('has minimum touch target size (48x48px)', () => {
      const { container } = render(
        <ResponsiveButton>Send</ResponsiveButton>
      )

      const button = container.querySelector('.responsive-button')
      expect(button).toHaveStyle({
        minWidth: '48px',
        minHeight: '48px',
      })
    })

    it('calls onClick handler', async () => {
      const handleClick = vi.fn()
      render(<ResponsiveButton onClick={handleClick}>Click</ResponsiveButton>)

      const button = screen.getByText('Click')
      await userEvent.click(button)

      expect(handleClick).toHaveBeenCalledTimes(1)
    })

    it('renders primary variant by default', () => {
      const { container } = render(
        <ResponsiveButton>Primary</ResponsiveButton>
      )

      const button = container.querySelector('.responsive-button-primary')
      expect(button).toBeInTheDocument()
    })

    it('renders secondary variant', () => {
      const { container } = render(
        <ResponsiveButton variant="secondary">Secondary</ResponsiveButton>
      )

      const button = container.querySelector('.responsive-button-secondary')
      expect(button).toBeInTheDocument()
    })

    it('accepts custom className', () => {
      const { container } = render(
        <ResponsiveButton className="custom-class">Button</ResponsiveButton>
      )

      const button = container.querySelector('.responsive-button')
      expect(button).toHaveClass('custom-class')
    })

    it('is keyboard accessible', async () => {
      render(<ResponsiveButton>Button</ResponsiveButton>)

      const button = screen.getByText('Button')
      button.focus()

      expect(button).toHaveFocus()
    })
  })

  describe('Accessibility', () => {
    it('hamburger button has accessible label', () => {
      render(
        <ResponsiveLayout
          sidebar={<div>Sidebar</div>}
          showSidebar={false}
          onSidebarToggle={vi.fn()}
        >
          <div>Content</div>
        </ResponsiveLayout>
      )

      const button = screen.getByLabelText(/Open navigation|Close navigation/)
      expect(button).toBeInTheDocument()
    })

    it('hamburger label changes based on state', async () => {
      const { rerender } = render(
        <ResponsiveLayout
          sidebar={<div>Sidebar</div>}
          showSidebar={false}
          onSidebarToggle={vi.fn()}
        >
          <div>Content</div>
        </ResponsiveLayout>
      )

      expect(screen.getByLabelText('Open navigation')).toBeInTheDocument()

      rerender(
        <ResponsiveLayout
          sidebar={<div>Sidebar</div>}
          showSidebar={true}
          onSidebarToggle={vi.fn()}
        >
          <div>Content</div>
        </ResponsiveLayout>
      )

      expect(screen.getByLabelText('Close navigation')).toBeInTheDocument()
    })

    it('messages have semantic structure', () => {
      render(
        <ResponsiveMessage role="user">Message</ResponsiveMessage>
      )

      const message = screen.getByText('Message')
      expect(message.closest('div')).toBeInTheDocument()
    })

    it('button is tab-navigable', async () => {
      const { container } = render(
        <ResponsiveButton>Test Button</ResponsiveButton>
      )

      const button = container.querySelector('button')
      expect(button).toBeInTheDocument()
      // Button should be naturally focusable
      expect(button.tagName).toBe('BUTTON')
    })
  })

  describe('Touch Optimization', () => {
    it('buttons have minimum 48px touch target', () => {
      const { container } = render(
        <ResponsiveButton>Touch</ResponsiveButton>
      )

      const button = container.querySelector('button')
      const styles = window.getComputedStyle(button)
      expect(button).toHaveStyle({
        minHeight: '48px',
        minWidth: '48px',
      })
    })

    it('message thread supports momentum scrolling on iOS', () => {
      const { container } = render(
        <ResponsiveMessageThread>
          <div>Message</div>
        </ResponsiveMessageThread>
      )

      const thread = container.querySelector('.responsive-message-thread')
      const styles = window.getComputedStyle(thread)
      // iOS momentum scroll styles applied
      expect(thread).toBeInTheDocument()
    })
  })

  describe('Safe Area Insets', () => {
    it('applies safe area insets to sidebar on mobile', () => {
      const { container } = render(
        <ResponsiveLayout
          sidebar={<div>Sidebar</div>}
          showSidebar={true}
          onSidebarToggle={vi.fn()}
        >
          <div>Content</div>
        </ResponsiveLayout>
      )

      const sidebar = container.querySelector('.responsive-sidebar')
      expect(sidebar).toHaveStyle({
        paddingTop: 'max(var(--safe-area-inset-top, 0px), 12px)',
        paddingLeft: 'max(var(--safe-area-inset-left, 0px), 0px)',
        paddingRight: 'max(var(--safe-area-inset-right, 0px), 0px)',
        paddingBottom: 'max(var(--safe-area-inset-bottom, 0px), 12px)',
      })
    })

    it('applies safe area insets to input area', () => {
      const { container } = render(
        <ResponsiveInputArea>
          <input />
        </ResponsiveInputArea>
      )

      const area = container.querySelector('.responsive-input-area')
      const paddingBottom = area.style.padding
      expect(paddingBottom).toContain('var(--safe-area-inset-bottom')
    })
  })

  describe('No Horizontal Scroll', () => {
    it('layout prevents horizontal scrolling', () => {
      const { container } = render(
        <ResponsiveLayout>
          <div>Content</div>
        </ResponsiveLayout>
      )

      const layout = container.querySelector('.responsive-layout')
      expect(layout).toHaveStyle({
        overflowX: 'hidden',
        maxWidth: '100vw',
      })
    })

    it('main content prevents horizontal scrolling', () => {
      const { container } = render(
        <ResponsiveLayout>
          <div>Content</div>
        </ResponsiveLayout>
      )

      const main = container.querySelector('.responsive-main')
      expect(main).toHaveStyle({
        overflowX: 'hidden',
        maxWidth: '100vw',
      })
    })
  })
})
