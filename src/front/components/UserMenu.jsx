import { useState, useRef, useEffect } from 'react'

/**
 * UserMenu - Avatar with dropdown menu for user and workspace actions
 *
 * Props:
 * - email: User email for avatar letter and display
 * - workspaceName: Workspace name to display
 * - workspaceId: Workspace ID for actions
 * - collapsed: Render compact avatar-only trigger for collapsed sidebar
 * - onSwitchWorkspace: optional callback for switch action
 * - onCreateWorkspace: optional callback for create action
 * - onOpenUserSettings: optional callback for settings action
 * - onLogout: optional callback for logout action
 */
export default function UserMenu({
  email,
  workspaceName,
  workspaceId,
  collapsed = false,
  onSwitchWorkspace,
  onCreateWorkspace,
  onOpenUserSettings,
  onLogout,
}) {
  const [isOpen, setIsOpen] = useState(false)
  const menuRef = useRef(null)

  // Get first letter of email (uppercase) for avatar
  const avatarLetter = email ? email.charAt(0).toUpperCase() : '?'

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  useEffect(() => {
    function handleEscape(event) {
      if (event.key === 'Escape') {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('keydown', handleEscape)
    }

    return () => {
      document.removeEventListener('keydown', handleEscape)
    }
  }, [isOpen])

  const runAction = (action) => {
    if (typeof action === 'function') {
      action({ workspaceId })
    }
    setIsOpen(false)
  }

  const actionItems = [
    { key: 'switch', label: 'Switch workspace', onClick: onSwitchWorkspace },
    { key: 'create', label: 'Create workspace', onClick: onCreateWorkspace },
    { key: 'settings', label: 'User settings', onClick: onOpenUserSettings },
    { key: 'logout', label: 'Logout', onClick: onLogout },
  ]

  const menuId = 'sidebar-user-menu'
  const displayEmail = email || 'Signed in user'
  const showWorkspace = workspaceName && !workspaceName.includes('-')
  const workspaceLabel = showWorkspace
    ? `workspace: ${workspaceName}`
    : workspaceId ? `workspace id: ${workspaceId}` : 'workspace: not selected'

  return (
    <div
      className={`user-menu ${collapsed ? 'user-menu-collapsed' : ''}`}
      ref={menuRef}
    >
      <button
        className={`user-menu-trigger ${collapsed ? 'compact' : ''}`}
        onClick={() => setIsOpen(!isOpen)}
        aria-label="User menu"
        aria-expanded={isOpen}
        aria-haspopup="true"
        aria-controls={isOpen ? menuId : undefined}
      >
        <span className="user-avatar">{avatarLetter}</span>
        {!collapsed && (
          <span className="user-menu-trigger-meta">
            <span className="user-menu-trigger-primary">{displayEmail}</span>
            <span className="user-menu-trigger-secondary">{workspaceLabel}</span>
          </span>
        )}
      </button>

      {isOpen && (
        <div className="user-menu-dropdown" id={menuId} role="menu">
          <div className="user-menu-email">{displayEmail}</div>
          <div className="user-menu-workspace">{workspaceLabel}</div>
          <div className="user-menu-divider" />
          {actionItems.map((item) => {
            const disabled = typeof item.onClick !== 'function'
            return (
              <button
                key={item.key}
                className={`user-menu-item ${disabled ? 'user-menu-item-disabled' : ''}`}
                onClick={() => runAction(item.onClick)}
                role="menuitem"
                disabled={disabled}
              >
                {item.label}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
