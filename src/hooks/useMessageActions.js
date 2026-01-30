import { useState, useCallback, useRef, useEffect } from 'react'

/**
 * useMessageActions - Custom hook for managing message action state and logic
 *
 * Provides:
 * - Copy to clipboard functionality
 * - Edit mode management
 * - Delete confirmation
 * - Emoji reactions
 * - Reply/quote tracking
 * - Pin/unpin functionality
 * - Share/export functionality
 * - Keyboard shortcut handling
 *
 * @param {Object} options
 * @param {string} options.messageId - ID of the message
 * @param {string} options.messageContent - Content to copy
 * @param {string} options.messageRole - Role of message (user/assistant)
 * @param {Function} options.onCopy - Callback when message is copied
 * @param {Function} options.onEdit - Callback when edit is requested
 * @param {Function} options.onDelete - Callback when delete is confirmed
 * @param {Function} options.onReact - Callback when reaction is added
 * @param {Function} options.onReply - Callback when reply is selected
 * @param {Function} options.onPin - Callback when pin is toggled
 * @param {Function} options.onShare - Callback when share is selected
 * @returns {Object} Action state and handlers
 */
export function useMessageActions({
  messageId,
  messageContent = '',
  messageRole = 'user',
  onCopy,
  onEdit,
  onDelete,
  onReact,
  onReply,
  onPin,
  onShare,
} = {}) {
  const [copied, setCopied] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [editContent, setEditContent] = useState(messageContent)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [isPinned, setIsPinned] = useState(false)
  const [reactions, setReactions] = useState([])
  const [showActionMenu, setShowActionMenu] = useState(false)
  const [isReplying, setIsReplying] = useState(false)
  const actionMenuRef = useRef(null)
  const copyTimeoutRef = useRef(null)

  // Copy message to clipboard
  const handleCopy = useCallback(async () => {
    if (!messageContent) return

    try {
      await navigator.clipboard.writeText(messageContent)
      setCopied(true)
      onCopy?.(messageId)

      // Reset copy feedback after 2 seconds
      if (copyTimeoutRef.current) {
        clearTimeout(copyTimeoutRef.current)
      }
      copyTimeoutRef.current = setTimeout(() => {
        setCopied(false)
      }, 2000)
    } catch (err) {
      console.error('Failed to copy message:', err)
    }
  }, [messageContent, messageId, onCopy])

  // Start editing message
  const handleEditStart = useCallback(() => {
    if (messageRole !== 'user') return // Only user messages can be edited

    setIsEditing(true)
    setEditContent(messageContent)
    setShowActionMenu(false)
  }, [messageContent, messageRole])

  // Cancel editing
  const handleEditCancel = useCallback(() => {
    setIsEditing(false)
    setEditContent(messageContent)
  }, [messageContent])

  // Save edited message
  const handleEditSave = useCallback(() => {
    if (!editContent.trim()) return

    onEdit?.(messageId, editContent)
    setIsEditing(false)
  }, [editContent, messageId, onEdit])

  // Request message deletion with confirmation
  const handleDeleteRequest = useCallback(() => {
    setShowDeleteConfirm(true)
    setShowActionMenu(false)
  }, [])

  // Confirm deletion
  const handleDeleteConfirm = useCallback(() => {
    onDelete?.(messageId)
    setShowDeleteConfirm(false)
  }, [messageId, onDelete])

  // Cancel deletion
  const handleDeleteCancel = useCallback(() => {
    setShowDeleteConfirm(false)
  }, [])

  // Add or remove reaction
  const handleReact = useCallback((emoji) => {
    setReactions((prev) => {
      const exists = prev.includes(emoji)
      if (exists) {
        return prev.filter((e) => e !== emoji)
      }
      return [...prev, emoji]
    })
    onReact?.(messageId, emoji)
    setShowActionMenu(false)
  }, [messageId, onReact])

  // Handle reply
  const handleReply = useCallback(() => {
    setIsReplying(true)
    onReply?.(messageId, messageContent)
    setShowActionMenu(false)
  }, [messageId, messageContent, onReply])

  // Cancel reply
  const handleReplyCancel = useCallback(() => {
    setIsReplying(false)
  }, [])

  // Toggle pin status
  const handlePin = useCallback(() => {
    const newPinStatus = !isPinned
    setIsPinned(newPinStatus)
    onPin?.(messageId, newPinStatus)
    setShowActionMenu(false)
  }, [messageId, isPinned, onPin])

  // Handle share/export
  const handleShare = useCallback(() => {
    onShare?.(messageId, messageContent)
    setShowActionMenu(false)
  }, [messageId, messageContent, onShare])

  // Toggle action menu visibility
  const handleToggleActionMenu = useCallback(() => {
    setShowActionMenu((prev) => !prev)
  }, [])

  // Close action menu
  const handleCloseActionMenu = useCallback(() => {
    setShowActionMenu(false)
  }, [])

  // Handle keyboard shortcuts
  useEffect(() => {
    const handleKeydown = (event) => {
      // Only handle shortcuts when action menu is focused or message is selected
      if (!actionMenuRef.current) return

      const key = event.key.toLowerCase()
      const isCtrlOrCmd = event.ctrlKey || event.metaKey

      // Shortcuts that don't require Ctrl/Cmd
      switch (key) {
        case 'c':
          if (!isCtrlOrCmd) {
            event.preventDefault()
            handleCopy()
          }
          break
        case 'r':
          event.preventDefault()
          handleReply()
          break
        case 'e':
          if (messageRole === 'user') {
            event.preventDefault()
            handleEditStart()
          }
          break
        case 'd':
          event.preventDefault()
          handleDeleteRequest()
          break
        case 'p':
          event.preventDefault()
          handlePin()
          break
        case 's':
          event.preventDefault()
          handleShare()
          break
        case 'escape':
          handleCloseActionMenu()
          break
        default:
          break
      }
    }

    const menuElement = actionMenuRef.current
    if (menuElement) {
      menuElement.addEventListener('keydown', handleKeydown)
      return () => {
        menuElement.removeEventListener('keydown', handleKeydown)
      }
    }
  }, [
    messageRole,
    handleCopy,
    handleReply,
    handleEditStart,
    handleDeleteRequest,
    handlePin,
    handleShare,
    handleCloseActionMenu,
  ])

  // Clean up timeout on unmount
  useEffect(() => {
    return () => {
      if (copyTimeoutRef.current) {
        clearTimeout(copyTimeoutRef.current)
      }
    }
  }, [])

  return {
    // State
    copied,
    isEditing,
    editContent,
    showDeleteConfirm,
    isPinned,
    reactions,
    showActionMenu,
    isReplying,

    // Setters
    setEditContent,

    // Handlers
    handleCopy,
    handleEditStart,
    handleEditCancel,
    handleEditSave,
    handleDeleteRequest,
    handleDeleteConfirm,
    handleDeleteCancel,
    handleReact,
    handleReply,
    handleReplyCancel,
    handlePin,
    handleShare,
    handleToggleActionMenu,
    handleCloseActionMenu,

    // Refs
    actionMenuRef,
  }
}

export default useMessageActions
