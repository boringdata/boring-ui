import React, { useState, useCallback, useMemo } from 'react'
import { Plus, Search, Archive, Trash2, AlertCircle } from 'lucide-react'
import ChatHistoryList from './ChatHistoryList'
import '../../styles/sidebar.css'

/**
 * ChatSidebar Component - Main sidebar for chat history and organization
 *
 * Provides:
 * - Chat history list with multiple views
 * - Create new chat button
 * - Search in sidebar
 * - Pin/unpin chats
 * - Archive chats
 * - Delete chats
 * - Drag-to-reorder
 * - Chat folders
 * - Unread indicators
 * - Recently accessed timestamps
 *
 * @param {Object} props
 * @param {Array} props.chats - Array of chat objects
 * @param {string} props.activeChatId - Currently selected chat ID
 * @param {Function} props.onSelectChat - Callback when chat is selected
 * @param {Function} props.onNewChat - Callback to create new chat
 * @param {Function} props.onPinChat - Callback when chat is pinned
 * @param {Function} props.onArchiveChat - Callback when chat is archived
 * @param {Function} props.onDeleteChat - Callback when chat is deleted
 * @param {Function} props.onRenameChat - Callback when chat is renamed
 * @param {Function} props.onReorderChats - Callback when chats are reordered
 * @param {boolean} props.isCollapsed - Whether sidebar is collapsed
 * @param {string} props.className - Additional CSS classes
 * @returns {React.ReactElement}
 */
const ChatSidebar = React.forwardRef(
  (
    {
      chats = [],
      activeChatId = null,
      onSelectChat,
      onNewChat,
      onPinChat,
      onArchiveChat,
      onDeleteChat,
      onRenameChat,
      onReorderChats,
      isCollapsed = false,
      className = '',
    },
    ref,
  ) => {
    const [searchQuery, setSearchQuery] = useState('')
    const [showArchived, setShowArchived] = useState(false)
    const [draggedItemId, setDraggedItemId] = useState(null)
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
    const [chatToDelete, setChatToDelete] = useState(null)

    // Filter and organize chats
    const organizedzchats = useMemo(() => {
      let filtered = [...chats]

      // Filter by search query
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase()
        filtered = filtered.filter(
          (chat) =>
            chat.title?.toLowerCase().includes(query) ||
            chat.preview?.toLowerCase().includes(query),
        )
      }

      // Filter by archive status
      filtered = filtered.filter((chat) => chat.isArchived === showArchived)

      // Sort: pinned first, then by last accessed
      return filtered.sort((a, b) => {
        if (a.isPinned !== b.isPinned) {
          return a.isPinned ? -1 : 1
        }
        return new Date(b.lastAccessed || 0) - new Date(a.lastAccessed || 0)
      })
    }, [chats, searchQuery, showArchived])

    const pinnedCount = useMemo(
      () => chats.filter((c) => c.isPinned && !c.isArchived).length,
      [chats],
    )

    const archivedCount = useMemo(
      () => chats.filter((c) => c.isArchived).length,
      [chats],
    )

    // Handle drag and drop
    const handleDragStart = useCallback((chatId, e) => {
      setDraggedItemId(chatId)
      e.dataTransfer.effectAllowed = 'move'
    }, [])

    const handleDragEnd = useCallback(() => {
      setDraggedItemId(null)
    }, [])

    const handleDragOver = useCallback((e) => {
      e.preventDefault()
      e.dataTransfer.dropEffect = 'move'
    }, [])

    const handleDrop = useCallback(
      (targetChatId, e) => {
        e.preventDefault()
        e.stopPropagation()

        if (draggedItemId && draggedItemId !== targetChatId) {
          const draggedIndex = chats.findIndex((c) => c.id === draggedItemId)
          const targetIndex = chats.findIndex((c) => c.id === targetChatId)

          if (draggedIndex !== -1 && targetIndex !== -1) {
            const newChats = [...chats]
            const [draggedChat] = newChats.splice(draggedIndex, 1)
            newChats.splice(targetIndex, 0, draggedChat)
            onReorderChats?.(newChats)
          }
        }

        setDraggedItemId(null)
      },
      [chats, draggedItemId, onReorderChats],
    )

    // Handle delete confirmation
    const handleDeleteRequest = useCallback((chatId) => {
      setChatToDelete(chatId)
      setShowDeleteConfirm(true)
    }, [])

    const handleDeleteConfirm = useCallback(() => {
      if (chatToDelete) {
        onDeleteChat?.(chatToDelete)
      }
      setShowDeleteConfirm(false)
      setChatToDelete(null)
    }, [chatToDelete, onDeleteChat])

    const sidebarClasses = `
      chat-sidebar
      ${isCollapsed ? 'chat-sidebar-collapsed' : ''}
      ${className}
    `.trim()

    return (
      <aside ref={ref} className={sidebarClasses}>
        {/* Header */}
        <div className="chat-sidebar-header">
          <h1 className="chat-sidebar-title">Chats</h1>
          <button
            className="chat-sidebar-new-button"
            onClick={onNewChat}
            title="New chat"
            aria-label="Create new chat"
          >
            <Plus size={20} />
            {!isCollapsed && <span>New Chat</span>}
          </button>
        </div>

        {/* Search */}
        {!isCollapsed && (
          <div className="chat-sidebar-search-container">
            <Search size={16} className="chat-sidebar-search-icon" />
            <input
              type="text"
              className="chat-sidebar-search-input"
              placeholder="Search chats..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label="Search chats"
            />
          </div>
        )}

        {/* Chat List */}
        <div className="chat-sidebar-list">
          {organizedzchats.length === 0 ? (
            <div className="chat-sidebar-empty">
              <p>
                {searchQuery
                  ? 'No chats match your search'
                  : showArchived
                    ? 'No archived chats'
                    : 'No chats yet'}
              </p>
            </div>
          ) : (
            <>
              {/* Pinned Section */}
              {pinnedCount > 0 && !showArchived && (
                <div className="chat-sidebar-section">
                  <div className="chat-sidebar-section-header">
                    Pinned ({pinnedCount})
                  </div>
                  <div className="chat-sidebar-section-content">
                    {organizedzchats
                      .filter((chat) => chat.isPinned)
                      .map((chat) => (
                        <div
                          key={chat.id}
                          onDragOver={handleDragOver}
                          onDrop={(e) => handleDrop(chat.id, e)}
                        >
                          <ChatHistoryList
                            chatId={chat.id}
                            title={chat.title}
                            preview={chat.preview}
                            lastAccessed={chat.lastAccessed}
                            isPinned={chat.isPinned}
                            isArchived={chat.isArchived}
                            hasUnread={chat.hasUnread}
                            isActive={chat.id === activeChatId}
                            onSelect={onSelectChat}
                            onPin={onPinChat}
                            onArchive={onArchiveChat}
                            onDelete={handleDeleteRequest}
                            onRename={onRenameChat}
                            onDragStart={handleDragStart}
                            onDragEnd={handleDragEnd}
                            isDragging={draggedItemId === chat.id}
                          />
                        </div>
                      ))}
                  </div>
                </div>
              )}

              {/* Recent Section */}
              {organizedzchats.filter((c) => !c.isPinned).length > 0 && (
                <div className="chat-sidebar-section">
                  <div className="chat-sidebar-section-header">
                    {showArchived ? 'Archived' : 'Recent'}
                  </div>
                  <div className="chat-sidebar-section-content">
                    {organizedzchats
                      .filter((c) => !c.isPinned)
                      .map((chat) => (
                        <div
                          key={chat.id}
                          onDragOver={handleDragOver}
                          onDrop={(e) => handleDrop(chat.id, e)}
                        >
                          <ChatHistoryList
                            chatId={chat.id}
                            title={chat.title}
                            preview={chat.preview}
                            lastAccessed={chat.lastAccessed}
                            isPinned={chat.isPinned}
                            isArchived={chat.isArchived}
                            hasUnread={chat.hasUnread}
                            isActive={chat.id === activeChatId}
                            onSelect={onSelectChat}
                            onPin={onPinChat}
                            onArchive={onArchiveChat}
                            onDelete={handleDeleteRequest}
                            onRename={onRenameChat}
                            onDragStart={handleDragStart}
                            onDragEnd={handleDragEnd}
                            isDragging={draggedItemId === chat.id}
                          />
                        </div>
                      ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        {!isCollapsed && archivedCount > 0 && !showArchived && (
          <div className="chat-sidebar-footer">
            <button
              className="chat-sidebar-footer-button"
              onClick={() => setShowArchived(true)}
            >
              <Archive size={16} />
              <span>
                Archived Chats ({archivedCount})
              </span>
            </button>
          </div>
        )}

        {showArchived && (
          <div className="chat-sidebar-footer">
            <button
              className="chat-sidebar-footer-button"
              onClick={() => setShowArchived(false)}
            >
              <Archive size={16} />
              <span>Back to Recent</span>
            </button>
          </div>
        )}

        {/* Delete Confirmation */}
        {showDeleteConfirm && (
          <div className="chat-sidebar-delete-confirm">
            <div className="chat-sidebar-confirm-container">
              <div className="chat-sidebar-confirm-content">
                <AlertCircle size={20} />
                <div>
                  <p className="chat-sidebar-confirm-title">Delete chat?</p>
                  <p className="chat-sidebar-confirm-text">
                    This cannot be undone.
                  </p>
                </div>
              </div>
              <div className="chat-sidebar-confirm-buttons">
                <button
                  className="chat-sidebar-button-secondary"
                  onClick={() => setShowDeleteConfirm(false)}
                >
                  Cancel
                </button>
                <button
                  className="chat-sidebar-button-danger"
                  onClick={handleDeleteConfirm}
                >
                  Delete
                </button>
              </div>
            </div>
          </div>
        )}
      </aside>
    )
  },
)

ChatSidebar.displayName = 'ChatSidebar'

export default ChatSidebar
