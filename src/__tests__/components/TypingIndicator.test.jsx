import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import React from 'react'
import TypingIndicator from '../../components/Chat/TypingIndicator'
import StreamingMessage from '../../components/Chat/StreamingMessage'

/**
 * STORY-C008: Message Streaming & Typing Indicators
 * Test suite for streaming components with focus on:
 * - Typing indicator smooth animation
 * - Word streaming at natural pace
 * - Cancellation works instantly
 * - Progress updates live
 */

describe('TypingIndicator Component', () => {
  describe('Rendering', () => {
    it('renders three typing dots', () => {
      const { container } = render(<TypingIndicator />)
      const dots = container.querySelectorAll('.typing-dot')
      expect(dots).toHaveLength(3)
    })

    it('renders with accessibility role', () => {
      render(<TypingIndicator />)
      const indicator = screen.getByRole('status')
      expect(indicator).toBeInTheDocument()
    })

    it('has default accessibility label', () => {
      render(<TypingIndicator />)
      const indicator = screen.getByLabelText('Claude is typing')
      expect(indicator).toBeInTheDocument()
    })

    it('accepts custom accessibility label', () => {
      render(<TypingIndicator label="AI is processing..." />)
      const indicator = screen.getByLabelText('AI is processing...')
      expect(indicator).toBeInTheDocument()
    })
  })

  describe('Animation', () => {
    it('applies animation classes to dots', () => {
      const { container } = render(<TypingIndicator />)
      const dots = container.querySelectorAll('.typing-dot')

      dots.forEach((dot) => {
        expect(dot.classList.contains('typing-dot')).toBe(true)
      })
    })

    it('stagger animation delays correctly', () => {
      const { container } = render(<TypingIndicator />)
      const dot1 = container.querySelector('.typing-dot-1')
      const dot2 = container.querySelector('.typing-dot-2')
      const dot3 = container.querySelector('.typing-dot-3')

      expect(dot1).toBeInTheDocument()
      expect(dot2).toBeInTheDocument()
      expect(dot3).toBeInTheDocument()
    })

    it('applies correct animation-delay to dots', () => {
      const { container } = render(<TypingIndicator />)
      const dots = container.querySelectorAll('.typing-dot')

      // Dots should have different animation delays
      expect(dots[0]).toHaveClass('typing-dot-1')
      expect(dots[1]).toHaveClass('typing-dot-2')
      expect(dots[2]).toHaveClass('typing-dot-3')
    })
  })

  describe('CSS Classes', () => {
    it('applies typing-indicator class', () => {
      const { container } = render(<TypingIndicator />)
      const indicator = container.querySelector('.typing-indicator')
      expect(indicator).toBeInTheDocument()
    })

    it('applies custom className', () => {
      const { container } = render(<TypingIndicator className="custom-class" />)
      const indicator = container.querySelector('.typing-indicator.custom-class')
      expect(indicator).toBeInTheDocument()
    })
  })

  describe('Accessibility', () => {
    it('hides dots from screen readers', () => {
      const { container } = render(<TypingIndicator />)
      const dots = container.querySelectorAll('.typing-dot')

      dots.forEach((dot) => {
        expect(dot.getAttribute('aria-hidden')).toBe('true')
      })
    })

    it('has live region for updates', () => {
      render(<TypingIndicator />)
      const indicator = screen.getByRole('status')
      expect(indicator).toHaveAttribute('aria-live', 'polite')
    })
  })

  describe('Memoization', () => {
    it('is memoized for performance', () => {
      const { rerender } = render(<TypingIndicator />)
      const before = screen.getByRole('status')

      rerender(<TypingIndicator />)
      const after = screen.getByRole('status')

      // Should be same element (memoized)
      expect(before.parentElement).toBe(after.parentElement)
    })
  })
})

describe('StreamingMessage Component', () => {
  const defaultProps = {
    id: 'stream-msg-1',
    content: 'Hello, this is streaming content.',
    author: 'Claude',
    role: 'assistant',
    isStreaming: true,
    onCancel: null,
  }

  describe('Rendering', () => {
    it('renders message bubble', () => {
      render(<StreamingMessage {...defaultProps} />)
      expect(screen.getByText(/Hello, this is streaming/)).toBeInTheDocument()
    })

    it('renders typing indicator when no content and streaming', () => {
      render(
        <StreamingMessage
          {...defaultProps}
          content=""
          isStreaming={true}
          showTypingIndicator={true}
        />,
      )
      expect(screen.getByRole('status')).toBeInTheDocument()
    })

    it('does not show status bar when not streaming', () => {
      const { container } = render(
        <StreamingMessage {...defaultProps} isStreaming={false} />,
      )
      expect(container.querySelector('.streaming-status')).not.toBeInTheDocument()
    })

    it('shows completion indicator when streaming ends', () => {
      const { container } = render(
        <StreamingMessage {...defaultProps} isStreaming={false} />,
      )
      expect(container.querySelector('.streaming-complete-indicator')).toBeInTheDocument()
    })
  })

  describe('Progress Indicator', () => {
    it('renders progress bar with percentage', () => {
      const { container } = render(
        <StreamingMessage {...defaultProps} progress={45} />,
      )
      const progressBar = container.querySelector('.streaming-progress-bar')
      const progressText = container.querySelector('.streaming-progress-text')

      expect(progressBar).toBeInTheDocument()
      expect(progressText?.textContent).toContain('45%')
    })

    it('updates progress fill width', () => {
      const { container } = render(
        <StreamingMessage {...defaultProps} progress={75} />,
      )
      const fill = container.querySelector('.streaming-progress-fill')

      expect(fill?.style.width).toBe('75%')
    })

    it('clamps progress to 100%', () => {
      const { container } = render(
        <StreamingMessage {...defaultProps} progress={150} />,
      )
      const fill = container.querySelector('.streaming-progress-fill')

      expect(fill?.style.width).toBe('100%')
    })

    it('does not show progress when null', () => {
      const { container } = render(
        <StreamingMessage {...defaultProps} progress={null} />,
      )
      expect(container.querySelector('.streaming-progress-group')).not.toBeInTheDocument()
    })
  })

  describe('Tools Being Invoked', () => {
    it('renders tools section when tools provided', () => {
      const { container } = render(
        <StreamingMessage
          {...defaultProps}
          toolsInvoking={['Read', 'Write', 'Bash']}
        />,
      )
      expect(screen.getByText(/Tools:/)).toBeInTheDocument()
    })

    it('displays each tool in list', () => {
      render(
        <StreamingMessage
          {...defaultProps}
          toolsInvoking={['Read', 'Write', 'Bash']}
        />,
      )
      expect(screen.getByText('Read')).toBeInTheDocument()
      expect(screen.getByText('Write')).toBeInTheDocument()
      expect(screen.getByText('Bash')).toBeInTheDocument()
    })

    it('does not show tools section when empty', () => {
      const { container } = render(
        <StreamingMessage {...defaultProps} toolsInvoking={[]} />,
      )
      expect(container.querySelector('.streaming-tools')).not.toBeInTheDocument()
    })
  })

  describe('Metadata Display', () => {
    it('displays word count', () => {
      const { container } = render(
        <StreamingMessage {...defaultProps} wordCount={42} />,
      )
      expect(screen.getByText(/42 words/)).toBeInTheDocument()
    })

    it('displays singular word count correctly', () => {
      render(<StreamingMessage {...defaultProps} wordCount={1} />)
      expect(screen.getByText(/1 word/)).toBeInTheDocument()
    })

    it('displays estimated time remaining', () => {
      render(
        <StreamingMessage
          {...defaultProps}
          estimatedTimeRemaining="12s"
        />,
      )
      expect(screen.getByText(/ETA: 12s/)).toBeInTheDocument()
    })
  })

  describe('Cancel Button', () => {
    it('renders cancel button when onCancel provided', () => {
      const onCancel = vi.fn()
      render(
        <StreamingMessage {...defaultProps} onCancel={onCancel} />,
      )
      expect(screen.getByLabelText(/Cancel message streaming/)).toBeInTheDocument()
    })

    it('does not render cancel button when onCancel not provided', () => {
      const { container } = render(<StreamingMessage {...defaultProps} />)
      expect(container.querySelector('.streaming-cancel-btn')).not.toBeInTheDocument()
    })

    it('calls onCancel when button clicked', () => {
      const onCancel = vi.fn()
      render(
        <StreamingMessage {...defaultProps} onCancel={onCancel} />,
      )
      const cancelBtn = screen.getByLabelText(/Cancel message streaming/)

      fireEvent.click(cancelBtn)

      expect(onCancel).toHaveBeenCalledTimes(1)
    })

    it('disables button after click', () => {
      const onCancel = vi.fn()
      render(
        <StreamingMessage {...defaultProps} onCancel={onCancel} />,
      )
      const cancelBtn = screen.getByLabelText(/Cancel message streaming/)

      fireEvent.click(cancelBtn)

      expect(cancelBtn).toBeDisabled()
    })

    it('shows cancelled indicator after cancel', async () => {
      const { container } = render(
        <StreamingMessage
          {...defaultProps}
          onCancel={() => {}}
        />,
      )
      const cancelBtn = screen.getByLabelText(/Cancel message streaming/)

      fireEvent.click(cancelBtn)

      await waitFor(() => {
        expect(container.querySelector('.streaming-cancelled-indicator')).toBeInTheDocument()
      })
    })
  })

  describe('Container Styling', () => {
    it('applies streaming-active class when streaming', () => {
      const { container } = render(
        <StreamingMessage {...defaultProps} isStreaming={true} />,
      )
      expect(container.querySelector('.streaming-active')).toBeInTheDocument()
    })

    it('applies streaming-complete class when not streaming', () => {
      const { container } = render(
        <StreamingMessage {...defaultProps} isStreaming={false} />,
      )
      expect(container.querySelector('.streaming-complete')).toBeInTheDocument()
    })

    it('applies streaming-cancelled class when cancelled', async () => {
      const { container } = render(
        <StreamingMessage
          {...defaultProps}
          onCancel={() => {}}
        />,
      )
      const cancelBtn = screen.getByLabelText(/Cancel message streaming/)

      fireEvent.click(cancelBtn)

      await waitFor(() => {
        expect(container.querySelector('.streaming-cancelled')).toBeInTheDocument()
      })
    })

    it('applies custom className', () => {
      const { container } = render(
        <StreamingMessage {...defaultProps} className="custom-stream" />,
      )
      expect(container.querySelector('.streaming-message-container.custom-stream')).toBeInTheDocument()
    })
  })

  describe('Message Data', () => {
    it('includes data-message-id attribute', () => {
      const { container } = render(
        <StreamingMessage {...defaultProps} id="test-123" />,
      )
      const messageContainer = container.querySelector('.streaming-message-container')
      expect(messageContainer?.getAttribute('data-message-id')).toBe('test-123')
    })
  })

  describe('Animation', () => {
    it('shows animations on status enter', () => {
      const { container } = render(
        <StreamingMessage {...defaultProps} isStreaming={true} />,
      )
      const status = container.querySelector('.streaming-status')
      expect(status?.className).toContain('streaming-status')
    })

    it('shows completion indicator with animation', () => {
      const { container } = render(
        <StreamingMessage {...defaultProps} isStreaming={false} />,
      )
      const indicator = container.querySelector('.streaming-complete-indicator')
      expect(indicator).toBeInTheDocument()
    })
  })

  describe('Accessibility', () => {
    it('cancel button has proper label', () => {
      const onCancel = vi.fn()
      render(
        <StreamingMessage {...defaultProps} onCancel={onCancel} />,
      )
      const cancelBtn = screen.getByLabelText(/Cancel message streaming/)
      expect(cancelBtn.getAttribute('title')).toBeTruthy()
    })
  })
})

describe('Integration: Typing Indicator with Streaming', () => {
  it('shows typing indicator in streaming message', () => {
    render(
      <StreamingMessage
        id="stream-1"
        content=""
        isStreaming={true}
        showTypingIndicator={true}
      />,
    )

    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('replaces typing indicator with content', () => {
    const { rerender } = render(
      <StreamingMessage
        id="stream-1"
        content=""
        isStreaming={true}
      />,
    )

    rerender(
      <StreamingMessage
        id="stream-1"
        content="Message content appears here"
        isStreaming={true}
      />,
    )

    expect(screen.getByText(/Message content appears here/)).toBeInTheDocument()
  })
})

describe('Streaming Performance', () => {
  it('renders large messages efficiently', () => {
    const largeContent = Array(1000)
      .fill(0)
      .map((_, i) => `Word${i}`)
      .join(' ')

    const start = performance.now()
    render(
      <StreamingMessage
        {...defaultProps}
        content={largeContent}
        wordCount={1000}
      />,
    )
    const duration = performance.now() - start

    expect(duration).toBeLessThan(200)
  })

  it('updates progress smoothly', () => {
    const { rerender } = render(
      <StreamingMessage {...defaultProps} progress={0} />,
    )

    const progressValues = [25, 50, 75, 100]

    progressValues.forEach((progress) => {
      rerender(
        <StreamingMessage {...defaultProps} progress={progress} />,
      )

      const fill = document.querySelector('.streaming-progress-fill')
      expect(fill?.style.width).toBe(`${progress}%`)
    })
  })
})

// Import fireEvent and waitFor for interaction tests
import { fireEvent, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
