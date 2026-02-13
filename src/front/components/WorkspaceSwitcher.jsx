/**
 * Workspace switcher dropdown for the app header.
 *
 * Bead: bd-223o.14.2 (H2)
 *
 * Design: hard navigation on selection via window.location.assign.
 * The active workspace is determined by the URL path /w/{workspace_id}/app.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { ChevronDown, Plus } from 'lucide-react'

const getWorkspaceName = (ws) =>
  ws?.name || ws?.workspace_name || ws?.slug || ws?.id || 'Workspace'

const getWorkspaceId = (ws) =>
  ws?.id || ws?.workspace_id || ws?.workspaceId || null

export default function WorkspaceSwitcher({
  workspaces = [],
  selectedWorkspaceId = null,
  onSwitchWorkspace,
  onCreateWorkspace,
}) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef(null)

  const selectedWorkspace = workspaces.find(
    (ws) => getWorkspaceId(ws) === selectedWorkspaceId,
  )
  const otherWorkspaces = workspaces.filter(
    (ws) => getWorkspaceId(ws) !== selectedWorkspaceId,
  )

  const handleSelect = useCallback(
    (wsId) => {
      setOpen(false)
      if (wsId !== selectedWorkspaceId && onSwitchWorkspace) {
        onSwitchWorkspace(wsId)
      }
    },
    [selectedWorkspaceId, onSwitchWorkspace],
  )

  const handleCreate = useCallback(() => {
    setOpen(false)
    if (onCreateWorkspace) {
      onCreateWorkspace()
    }
  }, [onCreateWorkspace])

  // Close dropdown when clicking outside.
  useEffect(() => {
    if (!open) return
    const handleClickOutside = (event) => {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  // Close dropdown on Escape.
  useEffect(() => {
    if (!open) return
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        setOpen(false)
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [open])

  // Don't render if no workspaces.
  if (workspaces.length === 0) return null

  return (
    <div className="ws-switcher" ref={containerRef} data-testid="workspace-switcher">
      <button
        type="button"
        className="ws-switcher-trigger"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
        aria-haspopup="listbox"
        data-testid="workspace-switcher-trigger"
      >
        <span className="ws-switcher-name">
          {selectedWorkspace ? getWorkspaceName(selectedWorkspace) : 'Select workspace'}
        </span>
        <ChevronDown size={14} className={`ws-switcher-chevron ${open ? 'ws-switcher-chevron-open' : ''}`} />
      </button>

      {open && (
        <div className="ws-switcher-dropdown" role="listbox" data-testid="workspace-switcher-dropdown">
          {selectedWorkspace && (
            <div
              className="ws-switcher-item ws-switcher-item-active"
              role="option"
              aria-selected="true"
            >
              <span className="ws-switcher-item-name">{getWorkspaceName(selectedWorkspace)}</span>
              <span className="ws-switcher-item-badge">Current</span>
            </div>
          )}

          {otherWorkspaces.length > 0 && selectedWorkspace && (
            <div className="ws-switcher-divider" />
          )}

          {otherWorkspaces.map((ws) => {
            const wsId = getWorkspaceId(ws)
            return (
              <button
                key={wsId}
                type="button"
                className="ws-switcher-item ws-switcher-item-selectable"
                role="option"
                aria-selected="false"
                onClick={() => handleSelect(wsId)}
                data-testid={`workspace-option-${wsId}`}
              >
                <span className="ws-switcher-item-name">{getWorkspaceName(ws)}</span>
              </button>
            )
          })}

          <div className="ws-switcher-divider" />

          <button
            type="button"
            className="ws-switcher-item ws-switcher-item-create"
            onClick={handleCreate}
            data-testid="workspace-create-btn"
          >
            <Plus size={14} />
            <span>New workspace</span>
          </button>
        </div>
      )}
    </div>
  )
}
