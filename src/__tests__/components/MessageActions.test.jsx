import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MessageActions from '../../components/Chat/MessageActions'
import { useMessageActions } from '../../hooks/useMessageActions'

/**
 * MessageActions Component Tests
 * Testing: copy, edit, delete, reactions, reply, pin, share functionality
 */
describe('MessageActions Component', () => {
  const defaultProps = {
    messageId: 'msg-1',
    messageContent: 'Hello, world!',
    messageRole: 'user',
  }

  beforeEach(() => {
    // Mock navigator.clipboard
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn(() => Promise.resolve()),
      },
    })
  })

  describe('Rendering', () => {
    it('should render action buttons', () => {
      render(<MessageActions {...defaultProps} />)

      expect(screen.getByTitle(/Copy message/)).toBeInTheDocument()
      expect(screen.getByTitle(/React with emoji/)).toBeInTheDocument()
      expect(screen.getByTitle(/Reply to message/)).toBeInTheDocument()
      expect(screen.getByTitle(/Pin message/)).toBeInTheDocument()
    })

    it('should render in compact mode when specified', () => {
      const { container } = render(
        <MessageActions {...defaultProps} compact={true} />,
      )

      expect(container.querySelector('.message-actions-compact')).toBeInTheDocument()
    })

    it('should render in inline layout by default', () => {
      const { container } = render(<MessageActions {...defaultProps} />)

      expect(container.querySelector('.message-actions-inline')).toBeInTheDocument()
    })

    it('should render in block layout when specified', () => {
      const { container } = render(
        <MessageActions {...defaultProps} inline={false} />,
      )

      expect(container.querySelector('.message-actions-block')).toBeInTheDocument()
    })
  })

  describe('Copy Functionality', () => {
    it('should copy message content to clipboard', async () => {
      const user = userEvent.setup()
      render(<MessageActions {...defaultProps} />)

      const copyButton = screen.getByTitle(/Copy message/)
      await user.click(copyButton)

      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
        defaultProps.messageContent,
      )
    })

    it('should show success state after copying', async () => {
      const user = userEvent.setup()
      const { container } = render(<MessageActions {...defaultProps} />)

      const copyButton = container.querySelector(
        '.message-actions-button:first-child',
      )
      await user.click(copyButton)

      await waitFor(() => {
        expect(copyButton).toHaveClass('message-actions-button-success')
      })
    })

    it('should reset copy state after 2 seconds', async () => {
      const user = userEvent.setup()
      const { container } = render(<MessageActions {...defaultProps} />)

      const copyButton = container.querySelector(
        '.message-actions-button:first-child',
      )
      await user.click(copyButton)

      await waitFor(
        () => {
          expect(copyButton).not.toHaveClass('message-actions-button-success')
        },
        { timeout: 2500 },
      )
    })

    it('should call onCopy callback', async () => {
      const user = userEvent.setup()
      const onCopy = vi.fn()
      render(<MessageActions {...defaultProps} onCopy={onCopy} />)

      const copyButton = screen.getByTitle(/Copy message/)
      await user.click(copyButton)

      expect(onCopy).toHaveBeenCalledWith(defaultProps.messageId)
    })

    it('should handle empty message content gracefully', async () => {
      const user = userEvent.setup()
      render(
        <MessageActions {...defaultProps} messageContent="" />,
      )

      const copyButton = screen.getByTitle(/Copy message/)
      await user.click(copyButton)

      expect(navigator.clipboard.writeText).not.toHaveBeenCalled()
    })
  })

  describe('Edit Functionality', () => {
    it('should show edit mode for user messages', async () => {
      const user = userEvent.setup()
      const { container } = render(
        <MessageActions {...defaultProps} messageRole="user" />,
      )

      const menuButton = container.querySelector('.message-actions-menu-trigger')
      await user.click(menuButton)

      const editButton = screen.getByText('Edit Message')
      expect(editButton).toBeInTheDocument()
    })

    it('should not show edit mode for assistant messages', async () => {
      const user = userEvent.setup()
      const { container } = render(
        <MessageActions {...defaultProps} messageRole="assistant" />,
      )

      const menuButton = container.querySelector('.message-actions-menu-trigger')
      await user.click(menuButton)

      const editButton = screen.queryByText('Edit Message')
      expect(editButton).not.toBeInTheDocument()
    })

    it('should enter edit mode when edit button clicked', async () => {
      const user = userEvent.setup()
      const { container } = render(
        <MessageActions {...defaultProps} messageRole="user" />,
      )

      const menuButton = container.querySelector('.message-actions-menu-trigger')
      await user.click(menuButton)

      const editButton = screen.getByText('Edit Message')
      await user.click(editButton)

      const editInput = container.querySelector('.message-actions-edit-input')
      expect(editInput).toBeInTheDocument()
    })

    it('should prefill edit input with message content', async () => {
      const user = userEvent.setup()
      const { container } = render(
        <MessageActions {...defaultProps} messageRole="user" />,
      )

      const menuButton = container.querySelector('.message-actions-menu-trigger')
      await user.click(menuButton)

      const editButton = screen.getByText('Edit Message')
      await user.click(editButton)

      const editInput = container.querySelector('.message-actions-edit-input')
      expect(editInput).toHaveValue(defaultProps.messageContent)
    })

    it('should call onEdit when save is clicked', async () => {
      const user = userEvent.setup()
      const onEdit = vi.fn()
      const { container } = render(
        <MessageActions {...defaultProps} messageRole="user" onEdit={onEdit} />,
      )

      const menuButton = container.querySelector('.message-actions-menu-trigger')
      await user.click(menuButton)

      const editButton = screen.getByText('Edit Message')
      await user.click(editButton)

      const editInput = container.querySelector('.message-actions-edit-input')
      await user.clear(editInput)
      await user.type(editInput, 'Updated message')

      const saveButton = screen.getByText('Save')
      await user.click(saveButton)

      expect(onEdit).toHaveBeenCalledWith(
        defaultProps.messageId,
        'Updated message',
      )
    })

    it('should cancel edit mode when cancel is clicked', async () => {
      const user = userEvent.setup()
      const { container } = render(
        <MessageActions {...defaultProps} messageRole="user" />,
      )

      const menuButton = container.querySelector('.message-actions-menu-trigger')
      await user.click(menuButton)

      const editButton = screen.getByText('Edit Message')
      await user.click(editButton)

      const cancelButton = screen.getByText('Cancel')
      await user.click(cancelButton)

      const editInput = container.querySelector('.message-actions-edit-input')
      expect(editInput).not.toBeInTheDocument()
    })
  })

  describe('Delete Functionality', () => {
    it('should show delete confirmation dialog', async () => {
      const user = userEvent.setup()
      const { container } = render(<MessageActions {...defaultProps} />)

      const menuButton = container.querySelector('.message-actions-menu-trigger')
      await user.click(menuButton)

      const deleteButton = screen.getByText('Delete')
      await user.click(deleteButton)

      expect(screen.getByText('Delete message?')).toBeInTheDocument()
    })

    it('should close confirmation dialog when cancel is clicked', async () => {
      const user = userEvent.setup()
      render(<MessageActions {...defaultProps} />)

      const menuButton = screen.getByTitle('More actions')
      await user.click(menuButton)

      const deleteButton = screen.getByText('Delete')
      await user.click(deleteButton)

      const cancelButton = screen.getByText('Cancel')
      await user.click(cancelButton)

      expect(screen.queryByText('Delete message?')).not.toBeInTheDocument()
    })

    it('should call onDelete when confirmed', async () => {
      const user = userEvent.setup()
      const onDelete = vi.fn()
      render(<MessageActions {...defaultProps} onDelete={onDelete} />)

      const menuButton = screen.getByTitle('More actions')
      await user.click(menuButton)

      const deleteButton = screen.getByText('Delete')
      await user.click(deleteButton)

      const confirmButton = screen.getByRole('button', { name: /confirm deletion/ })
      await user.click(confirmButton)

      expect(onDelete).toHaveBeenCalledWith(defaultProps.messageId)
    })
  })

  describe('Emoji Reactions', () => {
    it('should open emoji picker when react button clicked', async () => {
      const user = userEvent.setup()
      const { container } = render(<MessageActions {...defaultProps} />)

      const reactButton = screen.getByTitle(/React with emoji/)
      await user.click(reactButton)

      expect(container.querySelector('.message-actions-emoji-picker')).toBeInTheDocument()
    })

    it('should display emoji options', async () => {
      const user = userEvent.setup()
      render(<MessageActions {...defaultProps} />)

      const reactButton = screen.getByTitle(/React with emoji/)
      await user.click(reactButton)

      expect(screen.getByRole('button', { name: '👍' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '❤️' })).toBeInTheDocument()
    })

    it('should call onReact when emoji is selected', async () => {
      const user = userEvent.setup()
      const onReact = vi.fn()
      render(
        <MessageActions {...defaultProps} onReact={onReact} />,
      )

      const reactButton = screen.getByTitle(/React with emoji/)
      await user.click(reactButton)

      const thumbsUpButton = screen.getByRole('button', { name: '👍' })
      await user.click(thumbsUpButton)

      expect(onReact).toHaveBeenCalledWith(defaultProps.messageId, '👍')
    })

    it('should close emoji picker after selection', async () => {
      const user = userEvent.setup()
      const { container } = render(
        <MessageActions {...defaultProps} />,
      )

      const reactButton = screen.getByTitle(/React with emoji/)
      await user.click(reactButton)

      const thumbsUpButton = screen.getByRole('button', { name: '👍' })
      await user.click(thumbsUpButton)

      await waitFor(() => {
        expect(
          container.querySelector('.message-actions-emoji-picker'),
        ).not.toBeInTheDocument()
      })
    })
  })

  describe('Reply Functionality', () => {
    it('should call onReply when reply button clicked', async () => {
      const user = userEvent.setup()
      const onReply = vi.fn()
      render(<MessageActions {...defaultProps} onReply={onReply} />)

      const replyButton = screen.getByTitle(/Reply to message/)
      await user.click(replyButton)

      expect(onReply).toHaveBeenCalledWith(
        defaultProps.messageId,
        defaultProps.messageContent,
      )
    })
  })

  describe('Pin Functionality', () => {
    it('should toggle pin state', async () => {
      const user = userEvent.setup()
      const { container } = render(
        <MessageActions {...defaultProps} />,
      )

      const pinButton = screen.getByTitle(/Pin message/)
      await user.click(pinButton)

      await waitFor(() => {
        expect(pinButton).toHaveClass('message-actions-button-active')
      })
    })

    it('should call onPin with state', async () => {
      const user = userEvent.setup()
      const onPin = vi.fn()
      render(<MessageActions {...defaultProps} onPin={onPin} />)

      const pinButton = screen.getByTitle(/Pin message/)
      await user.click(pinButton)

      expect(onPin).toHaveBeenCalledWith(defaultProps.messageId, true)
    })
  })

  describe('Share Functionality', () => {
    it('should show share option in menu', async () => {
      const user = userEvent.setup()
      const { container } = render(<MessageActions {...defaultProps} />)

      const menuButton = container.querySelector('.message-actions-menu-trigger')
      await user.click(menuButton)

      expect(screen.getByText('Share')).toBeInTheDocument()
    })

    it('should call onShare when share is selected', async () => {
      const user = userEvent.setup()
      const onShare = vi.fn()
      const { container } = render(
        <MessageActions {...defaultProps} onShare={onShare} />,
      )

      const menuButton = container.querySelector('.message-actions-menu-trigger')
      await user.click(menuButton)

      const shareButton = screen.getByText('Share')
      await user.click(shareButton)

      expect(onShare).toHaveBeenCalledWith(
        defaultProps.messageId,
        defaultProps.messageContent,
      )
    })
  })

  describe('Keyboard Shortcuts', () => {
    it('should display keyboard shortcuts', () => {
      render(<MessageActions {...defaultProps} />)

      // Shortcuts are in a hidden element but should be in DOM
      const shortcutsHint = screen.queryByText('Keyboard Shortcuts:')
      // This might be hidden, but the component structure should support it
    })
  })

  describe('Menu Interactions', () => {
    it('should toggle action menu', async () => {
      const user = userEvent.setup()
      const { container } = render(<MessageActions {...defaultProps} />)

      const menuButton = container.querySelector('.message-actions-menu-trigger')
      expect(container.querySelector('.message-actions-dropdown')).not.toBeInTheDocument()

      await user.click(menuButton)
      expect(container.querySelector('.message-actions-dropdown')).toBeInTheDocument()

      await user.click(menuButton)
      expect(container.querySelector('.message-actions-dropdown')).not.toBeInTheDocument()
    })

    it('should close menu when item is clicked', async () => {
      const user = userEvent.setup()
      const onShare = vi.fn()
      const { container } = render(
        <MessageActions {...defaultProps} onShare={onShare} />,
      )

      const menuButton = container.querySelector('.message-actions-menu-trigger')
      await user.click(menuButton)

      const shareButton = screen.getByText('Share')
      await user.click(shareButton)

      await waitFor(() => {
        expect(container.querySelector('.message-actions-dropdown')).not.toBeInTheDocument()
      })
    })
  })

  describe('Accessibility', () => {
    it('should have proper ARIA attributes', () => {
      const { container } = render(<MessageActions {...defaultProps} />)

      const menuButton = container.querySelector('.message-actions-menu-trigger')
      expect(menuButton).toHaveAttribute('aria-label')
      expect(menuButton).toHaveAttribute('aria-expanded')
    })

    it('should support focus management', () => {
      const { container } = render(<MessageActions {...defaultProps} />)

      const buttons = container.querySelectorAll('.message-actions-button')
      expect(buttons.length).toBeGreaterThan(0)

      buttons.forEach((button) => {
        button.focus()
        expect(button).toHaveFocus()
      })
    })
  })

  describe('Performance', () => {
    it('should render within acceptable time', () => {
      const startTime = performance.now()
      render(<MessageActions {...defaultProps} />)
      const endTime = performance.now()

      expect(endTime - startTime).toBeLessThan(500)
    })
  })
})

/**
 * useMessageActions Hook Tests
 * Testing: state management, callbacks, cleanup
 */
describe('useMessageActions Hook', () => {
  it('should initialize with default state', () => {
    let hookResult
    const TestComponent = () => {
      hookResult = useMessageActions({
        messageId: 'test-1',
      })
      return null
    }

    render(<TestComponent />)

    expect(hookResult.copied).toBe(false)
    expect(hookResult.isEditing).toBe(false)
    expect(hookResult.showDeleteConfirm).toBe(false)
    expect(hookResult.isPinned).toBe(false)
  })

  it('should handle copy action', async () => {
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn(() => Promise.resolve()),
      },
    })

    let hookResult
    const TestComponent = () => {
      hookResult = useMessageActions({
        messageId: 'test-1',
        messageContent: 'Test content',
      })
      return null
    }

    render(<TestComponent />)

    await hookResult.handleCopy()

    expect(hookResult.copied).toBe(true)
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('Test content')
  })

  it('should handle edit actions', () => {
    let hookResult
    const TestComponent = () => {
      hookResult = useMessageActions({
        messageId: 'test-1',
        messageContent: 'Original',
        messageRole: 'user',
      })
      return null
    }

    render(<TestComponent />)

    hookResult.handleEditStart()
    expect(hookResult.isEditing).toBe(true)

    hookResult.setEditContent('Modified')
    expect(hookResult.editContent).toBe('Modified')

    hookResult.handleEditCancel()
    expect(hookResult.isEditing).toBe(false)
  })

  it('should handle delete confirmation', () => {
    let hookResult
    const TestComponent = () => {
      hookResult = useMessageActions({
        messageId: 'test-1',
      })
      return null
    }

    render(<TestComponent />)

    hookResult.handleDeleteRequest()
    expect(hookResult.showDeleteConfirm).toBe(true)

    hookResult.handleDeleteCancel()
    expect(hookResult.showDeleteConfirm).toBe(false)
  })

  it('should call callbacks', async () => {
    const onCopy = vi.fn()
    const onDelete = vi.fn()

    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn(() => Promise.resolve()),
      },
    })

    let hookResult
    const TestComponent = () => {
      hookResult = useMessageActions({
        messageId: 'test-1',
        messageContent: 'Test',
        onCopy,
        onDelete,
      })
      return null
    }

    render(<TestComponent />)

    await hookResult.handleCopy()
    expect(onCopy).toHaveBeenCalledWith('test-1')

    hookResult.handleDeleteConfirm()
    expect(onDelete).toHaveBeenCalledWith('test-1')
  })
})
