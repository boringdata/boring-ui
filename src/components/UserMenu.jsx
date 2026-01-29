import { useState, useRef, useEffect } from 'react'

/**
 * UserMenu - Reusable avatar with dropdown menu for user actions
 *
 * A standalone, reusable component for displaying user information and actions.
 * Works in both cloud mode (with full user info) and local mode (minimal display).
 *
 * @typedef {Object} UserData
 * @property {string} [email] - User's email address
 * @property {string} [workspace] - Workspace name to display
 * @property {string} [avatar] - Avatar URL (if provided, shown instead of letter)
 * @property {string} [displayName] - Display name (used for avatar letter if no avatar URL)
 *
 * @param {Object} props
 * @param {UserData} [props.user] - User data object
 * @param {() => void} [props.onLogout] - Callback when logout is clicked
 * @param {boolean} [props.isCloudMode=true] - Whether running in cloud mode (shows full menu) or local mode (minimal)
 * @param {string} [props.className] - Additional CSS class names
 */
export default function UserMenu({ user = {}, onLogout, isCloudMode = true, className }) {
  const [isOpen, setIsOpen] = useState(false)
  const menuRef = useRef(null)

  const { email, workspace, avatar, displayName } = user

  // Determine what to show for avatar
  // Priority: avatar URL > displayName initial > email initial > '?'
  const getAvatarContent = () => {
    if (avatar) {
      return <img src={avatar} alt="User avatar" className="user-avatar-img" />
    }
    if (displayName) {
      return displayName.charAt(0).toUpperCase()
    }
    if (email) {
      return email.charAt(0).toUpperCase()
    }
    return '?'
  }

  // Show workspace name if available and not a UUID
  const showWorkspace = workspace && !workspace.includes('-')

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

  const handleLogout = () => {
    setIsOpen(false)
    if (onLogout) {
      onLogout()
    }
  }

  // Build class names
  const containerClassName = ['user-menu', className].filter(Boolean).join(' ')

  // In local mode, show minimal UI
  if (!isCloudMode) {
    return (
      <div className={containerClassName} ref={menuRef}>
        <button
          className="user-avatar user-avatar--local"
          onClick={() => setIsOpen(!isOpen)}
          aria-label="User menu"
          aria-expanded={isOpen}
          aria-haspopup="true"
        >
          {getAvatarContent()}
        </button>

        {isOpen && (
          <div className="user-menu-dropdown" role="menu">
            <div className="user-menu-info">Local Mode</div>
            {onLogout && (
              <>
                <div className="user-menu-divider" />
                <button
                  className="user-menu-item"
                  onClick={handleLogout}
                  role="menuitem"
                >
                  Exit
                </button>
              </>
            )}
          </div>
        )}
      </div>
    )
  }

  // Cloud mode - full user menu
  return (
    <div className={containerClassName} ref={menuRef}>
      <button
        className="user-avatar"
        onClick={() => setIsOpen(!isOpen)}
        aria-label="User menu"
        aria-expanded={isOpen}
        aria-haspopup="true"
      >
        {getAvatarContent()}
      </button>

      {isOpen && (
        <div className="user-menu-dropdown" role="menu">
          {(displayName || email) && (
            <div className="user-menu-header">
              {displayName && <div className="user-menu-name">{displayName}</div>}
              {email && <div className="user-menu-email">{email}</div>}
            </div>
          )}
          {showWorkspace && <div className="user-menu-workspace">workspace: {workspace}</div>}
          {onLogout && (
            <>
              <div className="user-menu-divider" />
              <button
                className="user-menu-item"
                onClick={handleLogout}
                role="menuitem"
              >
                Logout
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}
