import React, { useState, useCallback } from 'react'
import {
  Pin,
  Archive,
  Trash2,
  Edit2,
  Check,
  X,
  Ellipsis,
} from 'lucide-react'
import '../../styles/sidebar.css'

/**
 * ChatHistoryList Component - Individual chat item in sidebar history
 *
 * Displays:
 * - Chat title with inline editing
 * - Last message preview
 * - Last accessed timestamp
 * - Unread indicator
 * - Pin/archive/delete buttons
 * - Drag handle for reordering
 * - Three-dot action menu
 *
 * @param {Object} props
 * @param {string} props.chatId - Unique chat ID
 * @param {string} props.title - Chat title
 * @param {string} props.preview - Last message preview
 * @param {Date|string} props.lastAccessed - When chat was last accessed
 * @param {boolean} props.isPinned - Whether chat is pinned
 * @param {boolean} props.isArchived - Whether chat is archived
 * @param {boolean} props.hasUnread - Whether chat has unread messages
 * @param {boolean} props.isActive - Whether chat is currently selected
 * @param {Function} props.onSelect - Callback when chat is selected
 * @param {Function} props.onPin - Callback when pinned/unpinned
 * @param {Function} props.onArchive - Callback when archived
 * @param {Function} props.onDelete - Callback when deleted
 * @param {Function} props.onRename - Callback when renamed
 * @param {Function} props.onDragStart - Callback for drag start
 * @param {Function} props.onDragEnd - Callback for drag end
 * @param {boolean} props.isDragging - Whether item is being dragged
 * @returns {React.ReactElement}
 */
const ChatHistoryList = React.forwardRef(
  (
    {
      chatId,
      title = 'Untitled Chat',
      preview = 'No messages yet',
      lastAccessed = new Date(),
      isPinned = false,
      isArchived = false,
      hasUnread = false,
      isActive = false,
      onSelect,
      onPin,
      onArchive,
      onDelete,
      onRename,
      onDragStart,
      onDragEnd,
      isDragging = false,
      className = '',
    },
    ref,
  ) => {
    const [isEditing, setIsEditing] = useState(false)
    const [editTitle, setEditTitle] = useState(title)
    const [showMenu, setShowMenu] = useState(false)

    const formatTime = useCallback(() => {
      if (!lastAccessed) return 'Never'

      const date = lastAccessed instanceof Date ? lastAccessed : new Date(lastAccessed)
      const now = new Date()
      const diffMs = now - date
      const diffSeconds = Math.floor(diffMs / 1000)
      const diffMinutes = Math.floor(diffSeconds / 60)
      const diffHours = Math.floor(diffMinutes / 60)
      const diffDays = Math.floor(diffHours / 24)

      if (diffSeconds < 60) return 'Now'
      if (diffMinutes < 60) return `${diffMinutes}m ago`
      if (diffHours < 24) return `${diffHours}h ago`
      if (diffDays < 7) return `${diffDays}d ago`

      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      })
    }, [lastAccessed])

    const handleSaveEdit = useCallback(() => {
      if (editTitle.trim()) {
        onRename?.(chatId, editTitle)
      }
      setIsEditing(false)
      setEditTitle(title)
    }, [chatId, editTitle, title, onRename])

    const handleCancelEdit = useCallback(() => {
      setIsEditing(false)
      setEditTitle(title)
    }, [title])

    const handleKeyDown = useCallback(
      (e) => {
        if (e.key === 'Enter') {
          handleSaveEdit()
        } else if (e.key === 'Escape') {
          handleCancelEdit()
        }
      },
      [handleSaveEdit, handleCancelEdit],
    )

    const itemClasses = `
      chat-history-item
      ${isActive ? 'chat-history-item-active' : ''}
      ${isDragging ? 'chat-history-item-dragging' : ''}
      ${isArchived ? 'chat-history-item-archived' : ''}
      ${className}
    `.trim()

    return (
      <div
        ref={ref}
        className={itemClasses}
        draggable
        onDragStart={(e) => onDragStart?.(chatId, e)}
        onDragEnd={() => onDragEnd?.()}
        onClick={() => !isEditing && onSelect?.(chatId)}
      >
        {/* Drag Handle */}
        <div className="chat-history-drag-handle" title="Drag to reorder">
          <div className="chat-history-drag-icon" />
        </div>

        {/* Chat Content */}
        <div className="chat-history-content">
          {/* Title Section */}
          <div className="chat-history-header">
            {isEditing ? (
              <input
                type="text"
                className="chat-history-edit-input"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                onKeyDown={handleKeyDown}
                onClick={(e) => e.stopPropagation()}
                autoFocus
              />
            ) : (
              <h3 className="chat-history-title">{title}</h3>
            )}

            {/* Unread Indicator */}
            {hasUnread && <div className="chat-history-unread" />}
          </div>

          {/* Preview Text */}
          <p className="chat-history-preview">{preview}</p>

          {/* Timestamp */}
          <div className="chat-history-meta">
            <time className="chat-history-time">{formatTime()}</time>
          </div>
        </div>

        {/* Actions */}
        <div className="chat-history-actions">
          {isEditing ? (
            <>
              <button
                className="chat-history-action-button chat-history-action-primary"
                onClick={(e) => {
                  e.stopPropagation()
                  handleSaveEdit()
                }}
                title="Save"
                aria-label="Save chat name"
              >
                <Check size={16} />
              </button>
              <button
                className="chat-history-action-button"
                onClick={(e) => {
                  e.stopPropagation()
                  handleCancelEdit()
                }}
                title="Cancel"
                aria-label="Cancel editing"
              >
                <X size={16} />
              </button>
            </>
          ) : (
            <>
              {/* Pin Button */}
              <button
                className={`chat-history-action-button ${
                  isPinned ? 'chat-history-action-active' : ''
                }`}
                onClick={(e) => {
                  e.stopPropagation()
                  onPin?.(chatId, !isPinned)
                }}
                title={isPinned ? 'Unpin' : 'Pin'}
                aria-label={isPinned ? 'Unpin chat' : 'Pin chat'}
              >
                <Pin size={16} />
              </button>

              {/* Menu Button */}
              <div className="chat-history-menu-container">
                <button
                  className={`chat-history-action-button ${
                    showMenu ? 'chat-history-menu-open' : ''
                  }`}
                  onClick={(e) => {
                    e.stopPropagation()
                    setShowMenu(!showMenu)
                  }}
                  title="More options"
                  aria-label="More options"
                  aria-expanded={showMenu}
                >
                  <Ellipsis size={16} />
                </button>

                {/* Dropdown Menu */}
                {showMenu && (
                  <div className="chat-history-dropdown">
                    <button
                      className="chat-history-menu-item"
                      onClick={(e) => {
                        e.stopPropagation()
                        setIsEditing(true)
                        setShowMenu(false)
                      }}
                    >
                      <Edit2 size={14} />
                      <span>Rename</span>
                    </button>

                    <button
                      className="chat-history-menu-item"
                      onClick={(e) => {
                        e.stopPropagation()
                        onArchive?.(chatId, !isArchived)
                        setShowMenu(false)
                      }}
                    >
                      <Archive size={14} />
                      <span>{isArchived ? 'Unarchive' : 'Archive'}</span>
                    </button>

                    <div className="chat-history-menu-divider" />

                    <button
                      className="chat-history-menu-item chat-history-menu-item-danger"
                      onClick={(e) => {
                        e.stopPropagation()
                        onDelete?.(chatId)
                        setShowMenu(false)
                      }}
                    >
                      <Trash2 size={14} />
                      <span>Delete</span>
                    </button>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    )
  },
)

ChatHistoryList.displayName = 'ChatHistoryList'

export default ChatHistoryList
