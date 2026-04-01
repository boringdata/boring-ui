import React, { useCallback } from 'react'
import { Plus, Clock3, Layers3 } from 'lucide-react'
import UserMenu from '../../shared/components/UserMenu'

/**
 * NavRail - 48px icon strip, always visible on the left edge.
 *
 * Provides quick access to: new chat, sessions, and the Surface.
 * Clicking a destination toggles the BrowseDrawer open/closed.
 * Clicking the same active destination again closes the drawer (sets null).
 *
 * Props:
 *   activeDestination  - string|null  currently active drawer destination
 *   onDestinationChange - (dest: string|null) => void
 *   onNewChat          - () => void  create a new chat session
 */
export default function NavRail({
  activeDestination = null,
  onDestinationChange,
  onNewChat,
  onToggleSurface,
  surfaceOpen = false,
  shellContext = {},
}) {
  const {
    userEmail = '',
    workspaceName = '',
    workspaceId = '',
    onSwitchWorkspace,
    workspaceOptions = [],
    onCreateWorkspace,
    onOpenUserSettings,
    onOpenWorkspaceSettings,
    onLogout,
    userMenuStatusMessage = '',
    userMenuStatusTone = 'error',
    onUserMenuRetry,
    userMenuDisabledActions = [],
  } = shellContext

  const showUserMenu = Boolean(
    userEmail
      || workspaceName
      || workspaceId
      || onSwitchWorkspace
      || onCreateWorkspace
      || onOpenUserSettings
      || onOpenWorkspaceSettings
      || onLogout,
  )

  const toggle = useCallback(
    (destination) => {
      if (activeDestination === destination) {
        onDestinationChange(null)
      } else {
        onDestinationChange(destination)
      }
    },
    [activeDestination, onDestinationChange]
  )

  return (
    <nav
      className="nav-rail"
      role="navigation"
      aria-label="Main navigation"
      data-testid="nav-rail"
    >
      <div className="nav-rail-brand" aria-hidden="true" data-testid="nav-rail-brand">
        B
      </div>

      <button
        className="rail-icon-btn rail-new-icon"
        title="New chat"
        aria-label="New chat"
        data-testid="nav-rail-new-chat"
        onClick={onNewChat}
      >
        <Plus size={16} />
      </button>

      <div className="rail-sep" />

      <button
        className={`rail-icon-btn${activeDestination === 'sessions' ? ' active' : ''}`}
        title="Sessions"
        aria-label="Sessions"
        data-testid="nav-rail-history"
        onClick={() => toggle('sessions')}
      >
        <Clock3 size={17} />
      </button>
      <button
        className={`rail-icon-btn${surfaceOpen ? ' active' : ''}`}
        title="Surface (⌘2)"
        aria-label="Toggle Surface"
        data-testid="nav-rail-surface"
        onClick={onToggleSurface}
      >
        <Layers3 size={17} />
      </button>

      <div className="nav-rail-spacer" />

      {showUserMenu ? (
        <div className="nav-rail-footer" data-testid="nav-rail-footer">
          <UserMenu
            email={userEmail}
            workspaceName={workspaceName}
            workspaceId={workspaceId}
            collapsed
            statusMessage={userMenuStatusMessage}
            statusTone={userMenuStatusTone}
            onRetry={onUserMenuRetry}
            disabledActions={userMenuDisabledActions}
            showSwitchWorkspace={Boolean(onSwitchWorkspace)}
            onSwitchWorkspace={onSwitchWorkspace}
            workspaceOptions={workspaceOptions}
            onCreateWorkspace={onCreateWorkspace}
            onOpenUserSettings={onOpenUserSettings}
            onOpenWorkspaceSettings={onOpenWorkspaceSettings}
            onLogout={onLogout}
          />
        </div>
      ) : null}
    </nav>
  )
}
