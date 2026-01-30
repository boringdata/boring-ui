import React, { useState } from 'react'
import {
  Copy,
  Edit2,
  Trash2,
  MessageSquare,
  Pin,
  Share2,
  MoreVertical,
  X,
  Check,
  AlertCircle,
  Smile,
  Redo,
} from 'lucide-react'
import { useMessageActions } from '../../hooks/useMessageActions'
import '../../styles/message-actions.css'

/**
 * MessageActions Component - Message interaction menu and buttons
 *
 * Provides:
 * - Copy message button with visual feedback
 * - Edit message (for user messages only)
 * - Delete message with confirmation
 * - React to message with emoji
 * - Reply/quote message
 * - Share/export message
 * - Pin important messages
 * - Three-dot action menu
 * - Keyboard shortcuts
 * - Smooth animations
 *
 * @param {Object} props
 * @param {string} props.messageId - Unique message ID
 * @param {string} props.messageContent - Message content
 * @param {'user'|'assistant'} props.messageRole - Role of message author
 * @param {Function} props.onCopy - Callback when message copied
 * @param {Function} props.onEdit - Callback when message edited
 * @param {Function} props.onDelete - Callback when message deleted
 * @param {Function} props.onReact - Callback when emoji reaction added
 * @param {Function} props.onReply - Callback when reply selected
 * @param {Function} props.onPin - Callback when message pinned
 * @param {Function} props.onShare - Callback when share selected
 * @param {boolean} props.compact - Compact layout (hide text labels)
 * @param {boolean} props.inline - Inline layout (horizontal)
 * @returns {React.ReactElement}
 */
const MessageActions = React.forwardRef(
  (
    {
      messageId,
      messageContent = '',
      messageRole = 'assistant',
      onCopy,
      onEdit,
      onDelete,
      onReact,
      onReply,
      onPin,
      onShare,
      compact = false,
      inline = true,
      className = '',
    },
    ref,
  ) => {
    const {
      copied,
      isEditing,
      editContent,
      showDeleteConfirm,
      isPinned,
      showActionMenu,
      setEditContent,
      handleCopy,
      handleEditStart,
      handleEditCancel,
      handleEditSave,
      handleDeleteRequest,
      handleDeleteConfirm,
      handleDeleteCancel,
      handleReact,
      handleReply,
      handlePin,
      handleShare,
      handleToggleActionMenu,
      handleCloseActionMenu,
      actionMenuRef,
    } = useMessageActions({
      messageId,
      messageContent,
      messageRole,
      onCopy,
      onEdit,
      onDelete,
      onReact,
      onReply,
      onPin,
      onShare,
    })

    const [showEmojiPicker, setShowEmojiPicker] = useState(false)

    const commonEmojis = ['👍', '👎', '😂', '😮', '❤️', '🔥', '✨', '🎉']

    const containerClasses = `
      message-actions
      ${inline ? 'message-actions-inline' : 'message-actions-block'}
      ${compact ? 'message-actions-compact' : ''}
      ${className}
    `.trim()

    return (
      <div ref={ref} className={containerClasses}>
        {/* Edit Mode */}
        {isEditing && (
          <div className="message-actions-edit-mode">
            <div className="message-actions-edit-container">
              <textarea
                className="message-actions-edit-input"
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                placeholder="Edit message..."
                autoFocus
              />
              <div className="message-actions-edit-buttons">
                <button
                  className="message-actions-button message-actions-button-primary"
                  onClick={handleEditSave}
                  title="Save changes (Ctrl+Enter)"
                  aria-label="Save edited message"
                >
                  <Check size={16} />
                  {!compact && <span>Save</span>}
                </button>
                <button
                  className="message-actions-button message-actions-button-secondary"
                  onClick={handleEditCancel}
                  title="Cancel editing (Escape)"
                  aria-label="Cancel editing"
                >
                  <X size={16} />
                  {!compact && <span>Cancel</span>}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Delete Confirmation */}
        {showDeleteConfirm && (
          <div className="message-actions-delete-confirm">
            <div className="message-actions-confirm-container">
              <div className="message-actions-confirm-content">
                <AlertCircle size={20} className="message-actions-confirm-icon" />
                <div>
                  <p className="message-actions-confirm-title">Delete message?</p>
                  <p className="message-actions-confirm-text">
                    This action cannot be undone.
                  </p>
                </div>
              </div>
              <div className="message-actions-confirm-buttons">
                <button
                  className="message-actions-button message-actions-button-secondary"
                  onClick={handleDeleteCancel}
                  aria-label="Cancel deletion"
                >
                  Cancel
                </button>
                <button
                  className="message-actions-button message-actions-button-danger"
                  onClick={handleDeleteConfirm}
                  aria-label="Confirm deletion"
                >
                  Delete
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Reply Mode */}
        {/* Note: Reply functionality is typically handled at conversation level */}

        {/* Main Action Bar */}
        {!isEditing && !showDeleteConfirm && (
          <div className="message-actions-bar">
            {/* Quick Actions */}
            <div className="message-actions-group">
              {/* Copy Button */}
              <button
                className={`message-actions-button ${
                  copied ? 'message-actions-button-success' : ''
                }`}
                onClick={handleCopy}
                title={copied ? 'Copied!' : 'Copy message (C)'}
                aria-label="Copy message"
              >
                <Copy size={16} />
                {!compact && <span>{copied ? 'Copied' : 'Copy'}</span>}
              </button>

              {/* Emoji Reaction Button */}
              <div className="message-actions-emoji-container">
                <button
                  className="message-actions-button"
                  onClick={() => setShowEmojiPicker(!showEmojiPicker)}
                  title="React with emoji (Shift+R)"
                  aria-label="React to message"
                >
                  <Smile size={16} />
                  {!compact && <span>React</span>}
                </button>

                {/* Emoji Picker */}
                {showEmojiPicker && (
                  <div className="message-actions-emoji-picker">
                    <div className="message-actions-emoji-grid">
                      {commonEmojis.map((emoji) => (
                        <button
                          key={emoji}
                          className="message-actions-emoji-button"
                          onClick={() => {
                            handleReact(emoji)
                            setShowEmojiPicker(false)
                          }}
                          title={emoji}
                          aria-label={`React with ${emoji}`}
                        >
                          {emoji}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Reply Button */}
              <button
                className="message-actions-button"
                onClick={handleReply}
                title="Reply to message (R)"
                aria-label="Reply to message"
              >
                <MessageSquare size={16} />
                {!compact && <span>Reply</span>}
              </button>

              {/* Pin Button */}
              <button
                className={`message-actions-button ${
                  isPinned ? 'message-actions-button-active' : ''
                }`}
                onClick={handlePin}
                title={isPinned ? 'Unpin message (P)' : 'Pin message (P)'}
                aria-label={isPinned ? 'Unpin message' : 'Pin message'}
              >
                <Pin size={16} />
                {!compact && <span>{isPinned ? 'Pinned' : 'Pin'}</span>}
              </button>
            </div>

            {/* More Actions Menu */}
            <div className="message-actions-menu-container" ref={actionMenuRef}>
              <button
                className={`message-actions-button message-actions-menu-trigger ${
                  showActionMenu ? 'message-actions-menu-open' : ''
                }`}
                onClick={handleToggleActionMenu}
                title="More actions"
                aria-label="More actions"
                aria-expanded={showActionMenu}
              >
                <MoreVertical size={16} />
              </button>

              {/* Dropdown Menu */}
              {showActionMenu && (
                <div className="message-actions-dropdown">
                  {messageRole === 'user' && (
                    <button
                      className="message-actions-menu-item"
                      onClick={handleEditStart}
                      title="Edit message (E)"
                    >
                      <Edit2 size={16} />
                      <span>Edit Message</span>
                    </button>
                  )}

                  <button
                    className="message-actions-menu-item"
                    onClick={handleShare}
                    title="Share message (S)"
                  >
                    <Share2 size={16} />
                    <span>Share</span>
                  </button>

                  <div className="message-actions-menu-divider" />

                  <button
                    className="message-actions-menu-item message-actions-menu-item-danger"
                    onClick={handleDeleteRequest}
                    title="Delete message (D)"
                  >
                    <Trash2 size={16} />
                    <span>Delete</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Keyboard Shortcuts Help */}
        <div className="message-actions-shortcuts-hint">
          <div className="message-actions-shortcuts-title">Keyboard Shortcuts:</div>
          <div className="message-actions-shortcuts-grid">
            <div className="message-actions-shortcut">
              <kbd>C</kbd>
              <span>Copy</span>
            </div>
            <div className="message-actions-shortcut">
              <kbd>R</kbd>
              <span>Reply</span>
            </div>
            <div className="message-actions-shortcut">
              <kbd>P</kbd>
              <span>Pin</span>
            </div>
            {messageRole === 'user' && (
              <div className="message-actions-shortcut">
                <kbd>E</kbd>
                <span>Edit</span>
              </div>
            )}
            <div className="message-actions-shortcut">
              <kbd>D</kbd>
              <span>Delete</span>
            </div>
            <div className="message-actions-shortcut">
              <kbd>S</kbd>
              <span>Share</span>
            </div>
          </div>
        </div>
      </div>
    )
  },
)

MessageActions.displayName = 'MessageActions'

export default MessageActions
