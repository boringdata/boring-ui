import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import React from 'react'
import Message from '../../components/Chat/Message'
import MessageBubble from '../../components/Chat/MessageBubble'

/**
 * STORY-C001: Message Display Enhancement & Animations
 * Test suite for message components with focus on:
 * - Render performance (<100ms per message)
 * - Animation correctness
 * - Message grouping
 * - Skeleton loaders
 * - Timestamp formatting
 */

describe('Message Component', () => {
  const defaultProps = {
    id: 'msg-1',
    content: 'Hello, world!',
    author: 'Claude',
    role: 'assistant',
    timestamp: new Date('2024-01-30T10:30:00'),
  }

  describe('Rendering', () => {
    it('renders message with content', () => {
      render(<Message {...defaultProps} />)
      expect(screen.getByText('Hello, world!')).toBeInTheDocument()
    })

    it('renders with user role styling', () => {
      const { container } = render(
        <Message {...defaultProps} role="user" author="You" />,
      )
      const messageContainer = container.querySelector('.message-role-user')
      expect(messageContainer).toBeInTheDocument()
    })

    it('renders with assistant role styling', () => {
      const { container } = render(
        <Message {...defaultProps} role="assistant" />,
      )
      const messageContainer = container.querySelector('.message-role-assistant')
      expect(messageContainer).toBeInTheDocument()
    })

    it('renders author name when showGrouped is true', () => {
      render(<Message {...defaultProps} showGrouped={true} author="Claude" />)
      expect(screen.getByText('Claude')).toBeInTheDocument()
    })

    it('does not render author name when showGrouped is false', () => {
      const { container } = render(
        <Message {...defaultProps} showGrouped={false} />,
      )
      const header = container.querySelector('.message-header')
      expect(header).not.toBeInTheDocument()
    })

    it('renders empty state message', () => {
      render(<Message {...defaultProps} content="" />)
      expect(screen.getByText('(empty message)')).toBeInTheDocument()
    })
  })

  describe('Timestamp Formatting', () => {
    it('formats "just now" for recent messages', () => {
      const now = new Date()
      render(<Message {...defaultProps} timestamp={now} />)
      expect(screen.getByText('just now')).toBeInTheDocument()
    })

    it('formats minutes correctly', () => {
      const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000)
      render(<Message {...defaultProps} timestamp={fiveMinutesAgo} />)
      expect(screen.getByText(/5m ago/i)).toBeInTheDocument()
    })

    it('formats hours correctly', () => {
      const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60 * 1000)
      render(<Message {...defaultProps} timestamp={twoHoursAgo} />)
      expect(screen.getByText(/2h ago/i)).toBeInTheDocument()
    })

    it('formats days correctly', () => {
      const threeDaysAgo = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000)
      render(<Message {...defaultProps} timestamp={threeDaysAgo} />)
      expect(screen.getByText(/3d ago/i)).toBeInTheDocument()
    })

    it('handles invalid timestamps gracefully', () => {
      const { container } = render(
        <Message {...defaultProps} timestamp="invalid" />,
      )
      const timeElement = container.querySelector('.message-time')
      // Should exist but be empty or not show invalid text
      expect(timeElement?.textContent).not.toContain('Invalid')
    })

    it('handles missing timestamp', () => {
      const { container } = render(<Message {...defaultProps} timestamp={null} />)
      const timeElement = container.querySelector('.message-time')
      expect(timeElement?.textContent || '').toBe('')
    })
  })

  describe('Avatar Rendering', () => {
    it('renders user avatar with user initials', () => {
      const { container } = render(
        <Message {...defaultProps} role="user" author="Alice" showGrouped={true} />,
      )
      const avatar = container.querySelector('.avatar-user')
      expect(avatar).toBeInTheDocument()
      expect(avatar?.textContent).toBe('A')
    })

    it('renders assistant avatar', () => {
      const { container } = render(
        <Message {...defaultProps} role="assistant" showGrouped={true} />,
      )
      const avatar = container.querySelector('.avatar-assistant')
      expect(avatar).toBeInTheDocument()
      expect(avatar?.textContent).toBe('C')
    })

    it('applies fade-in animation to avatar', () => {
      const { container } = render(
        <Message {...defaultProps} showGrouped={true} />,
      )
      const avatar = container.querySelector('.message-avatar')
      expect(avatar?.classList.contains('animate-fade-in')).toBe(true)
    })
  })

  describe('Reactions', () => {
    it('renders reactions when provided', () => {
      const reactions = [{ emoji: '👍', count: 2, users: ['Alice', 'Bob'] }]
      const { container } = render(
        <Message {...defaultProps} reactions={reactions} />,
      )
      expect(screen.getByText('👍')).toBeInTheDocument()
      expect(screen.getByText('2')).toBeInTheDocument()
    })

    it('does not render reactions section when empty', () => {
      const { container } = render(
        <Message {...defaultProps} reactions={[]} />,
      )
      const reactionsSection = container.querySelector('.message-reactions')
      expect(reactionsSection).not.toBeInTheDocument()
    })

    it('renders multiple reactions in order', () => {
      const reactions = [
        { emoji: '👍', count: 1, users: ['Alice'] },
        { emoji: '❤️', count: 3, users: ['Bob', 'Carol', 'Dave'] },
        { emoji: '🎉', count: 1, users: ['Eve'] },
      ]
      render(<Message {...defaultProps} reactions={reactions} />)
      expect(screen.getByText('👍')).toBeInTheDocument()
      expect(screen.getByText('❤️')).toBeInTheDocument()
      expect(screen.getByText('🎉')).toBeInTheDocument()
    })

    it('applies scale-in animation to reactions', () => {
      const reactions = [{ emoji: '👍', count: 1, users: ['Alice'] }]
      const { container } = render(
        <Message {...defaultProps} reactions={reactions} />,
      )
      const reactionChip = container.querySelector('.reaction-chip')
      expect(reactionChip?.classList.contains('animate-scale-in')).toBe(true)
    })

    it('applies correct animation delay to reactions', () => {
      const reactions = [
        { emoji: '👍', count: 1, users: ['Alice'] },
        { emoji: '❤️', count: 1, users: ['Bob'] },
      ]
      const { container } = render(
        <Message {...defaultProps} reactions={reactions} animationDelay={100} />,
      )
      const reactionChips = container.querySelectorAll('.reaction-chip')
      // First reaction should have delay from animationDelay + 50ms
      expect(reactionChips[0].style.getPropertyValue('--animation-delay')).toMatch(
        /150ms/,
      )
    })
  })

  describe('Streaming State', () => {
    it('applies streaming class when isStreaming is true', () => {
      const { container } = render(
        <Message {...defaultProps} isStreaming={true} />,
      )
      expect(container.querySelector('.message-streaming')).toBeInTheDocument()
    })

    it('does not apply streaming class when isStreaming is false', () => {
      const { container } = render(
        <Message {...defaultProps} isStreaming={false} />,
      )
      expect(container.querySelector('.message-streaming')).not.toBeInTheDocument()
    })
  })

  describe('Animation and Performance', () => {
    it('applies animation delay to message container', () => {
      const { container } = render(
        <Message {...defaultProps} animationDelay={150} />,
      )
      const messageContainer = container.querySelector('.message-container')
      expect(
        messageContainer?.style.getPropertyValue('--animation-delay'),
      ).toBe('150ms')
    })

    it('monitors render performance', () => {
      const perfWarnSpy = vi.spyOn(console, 'warn')
      const start = performance.now()

      render(<Message {...defaultProps} />)

      const duration = performance.now() - start
      expect(duration).toBeLessThan(100)
      expect(perfWarnSpy).not.toHaveBeenCalled()

      perfWarnSpy.mockRestore()
    })

    it('applies slide animation classes', () => {
      const { container } = render(
        <Message {...defaultProps} />,
      )
      const bubble = container.querySelector('.message-bubble')
      expect(bubble?.classList.contains('animate-fade-in')).toBe(true)
      expect(bubble?.classList.contains('animate-slide-up')).toBe(true)
    })
  })

  describe('CSS Classes and Styling', () => {
    it('applies user bubble styling', () => {
      const { container } = render(
        <Message {...defaultProps} role="user" />,
      )
      const bubble = container.querySelector('.message-bubble-user')
      expect(bubble).toBeInTheDocument()
    })

    it('applies assistant bubble styling', () => {
      const { container } = render(
        <Message {...defaultProps} role="assistant" />,
      )
      const bubble = container.querySelector('.message-bubble-assistant')
      expect(bubble).toBeInTheDocument()
    })

    it('applies custom className', () => {
      const { container } = render(
        <Message {...defaultProps} className="custom-class" />,
      )
      const messageContainer = container.querySelector('.message-container')
      expect(messageContainer?.classList.contains('custom-class')).toBe(true)
    })
  })

  describe('Forward Ref', () => {
    it('forwards ref correctly', () => {
      const ref = { current: null }
      render(<Message {...defaultProps} ref={ref} />)
      expect(ref.current).toBeInTheDocument()
      expect(ref.current?.getAttribute('data-message-id')).toBe('msg-1')
    })
  })

  describe('Accessibility', () => {
    it('includes data-message-id for tracking', () => {
      const { container } = render(
        <Message {...defaultProps} id="accessible-msg-1" />,
      )
      const messageContainer = container.querySelector('.message-container')
      expect(messageContainer?.getAttribute('data-message-id')).toBe(
        'accessible-msg-1',
      )
    })

    it('includes title attribute on avatars', () => {
      const { container } = render(
        <Message {...defaultProps} author="Alice" showGrouped={true} />,
      )
      const avatar = container.querySelector('.avatar-user')
      expect(avatar?.getAttribute('title')).toBe('Alice')
    })
  })
})

describe('MessageBubble Component', () => {
  const defaultProps = {
    content: 'Test message content',
    isUser: false,
    isStreaming: false,
  }

  describe('Rendering', () => {
    it('renders message content', () => {
      render(<MessageBubble {...defaultProps} />)
      expect(screen.getByText('Test message content')).toBeInTheDocument()
    })

    it('renders empty message indicator', () => {
      render(<MessageBubble {...defaultProps} content="" />)
      expect(screen.getByText('(empty message)')).toBeInTheDocument()
    })

    it('renders skeleton loader when streaming without content', () => {
      const { container } = render(
        <MessageBubble {...defaultProps} isStreaming={true} content={null} />,
      )
      expect(container.querySelector('.message-skeleton')).toBeInTheDocument()
    })

    it('renders streaming indicator when streaming with content', () => {
      const { container } = render(
        <MessageBubble {...defaultProps} isStreaming={true} />,
      )
      expect(container.querySelector('.message-streaming-indicator')).toBeInTheDocument()
    })

    it('renders three skeleton lines', () => {
      const { container } = render(
        <MessageBubble {...defaultProps} isStreaming={true} content={null} />,
      )
      const skeletonLines = container.querySelectorAll('.skeleton-line')
      expect(skeletonLines.length).toBe(3)
    })

    it('renders three streaming dots', () => {
      const { container } = render(
        <MessageBubble {...defaultProps} isStreaming={true} />,
      )
      const streamingDots = container.querySelectorAll('.streaming-dot')
      expect(streamingDots.length).toBe(3)
    })
  })

  describe('Styling', () => {
    it('applies user bubble classes', () => {
      const { container } = render(
        <MessageBubble {...defaultProps} isUser={true} />,
      )
      const bubble = container.querySelector('.message-bubble')
      expect(bubble?.classList.contains('animate-fade-in')).toBe(true)
      expect(bubble?.classList.contains('animate-slide-up')).toBe(true)
    })

    it('applies assistant bubble classes', () => {
      const { container } = render(
        <MessageBubble {...defaultProps} isUser={false} />,
      )
      const bubble = container.querySelector('.message-bubble')
      expect(bubble?.classList.contains('animate-fade-in')).toBe(true)
    })

    it('applies custom bubble classes', () => {
      const { container } = render(
        <MessageBubble
          {...defaultProps}
          bubbleClasses="custom-bubble-class"
        />,
      )
      const bubble = container.querySelector('.custom-bubble-class')
      expect(bubble).toBeInTheDocument()
    })
  })

  describe('Memoization', () => {
    it('is memoized for performance', () => {
      const { rerender } = render(<MessageBubble {...defaultProps} />)
      const before = screen.getByText('Test message content')

      // Re-render with same props
      rerender(<MessageBubble {...defaultProps} />)
      const after = screen.getByText('Test message content')

      // Should be same DOM node (memoized)
      expect(before).toBe(after)
    })
  })
})

describe('Message Grouping Logic', () => {
  it('shows header for first message in group', () => {
    render(
      <div>
        <Message
          id="msg-1"
          content="First"
          author="Claude"
          role="assistant"
          timestamp={new Date()}
          showGrouped={true}
        />
        <Message
          id="msg-2"
          content="Second"
          author="Claude"
          role="assistant"
          timestamp={new Date()}
          showGrouped={false}
        />
      </div>,
    )

    const headers = screen.getAllByText('Claude')
    expect(headers.length).toBe(1) // Only first message shows author
  })
})

describe('Animation Performance', () => {
  it('respects reduced motion preference', () => {
    const { container } = render(
      <div style={{ '--prefers-reduced-motion': 'reduce' }}>
        <Message
          id="msg-1"
          content="Respects reduced motion"
          author="Claude"
          role="assistant"
          timestamp={new Date()}
        />
      </div>,
    )

    // Component should still render, just without animations
    expect(screen.getByText('Respects reduced motion')).toBeInTheDocument()
  })
})

describe('Integration Tests', () => {
  it('renders complete message with all features', () => {
    const reactions = [
      { emoji: '👍', count: 5, users: ['Alice', 'Bob'] },
      { emoji: '❤️', count: 2, users: ['Carol', 'Dave'] },
    ]

    const { container } = render(
      <Message
        id="complete-msg"
        content="This is a complete message example!"
        author="Claude Assistant"
        role="assistant"
        timestamp={new Date(Date.now() - 5 * 60 * 1000)}
        isStreaming={false}
        showGrouped={true}
        reactions={reactions}
        animationDelay={50}
      />,
    )

    // Check all elements are present
    expect(screen.getByText('This is a complete message example!')).toBeInTheDocument()
    expect(screen.getByText('Claude Assistant')).toBeInTheDocument()
    expect(screen.getByText(/5m ago/)).toBeInTheDocument()
    expect(screen.getByText('👍')).toBeInTheDocument()
    expect(screen.getByText('❤️')).toBeInTheDocument()
    expect(screen.getByText('5')).toBeInTheDocument() // First reaction count
    expect(screen.getByText('2')).toBeInTheDocument() // Second reaction count

    // Check animations are applied
    expect(container.querySelector('.animate-fade-in')).toBeInTheDocument()
    expect(container.querySelector('.animate-scale-in')).toBeInTheDocument()
  })
})
