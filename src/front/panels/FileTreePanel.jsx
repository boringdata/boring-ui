import React, { useState } from 'react'
import { ChevronRight } from 'lucide-react'
import FileTree from '../components/FileTree'
import GitChangesView from '../components/GitChangesView'
import UserMenu from '../components/UserMenu'
import Tooltip from '../components/Tooltip'
import { LeftPaneHeader } from '../components/SidebarSectionHeader'

export default function FileTreePanel({ params }) {
  const {
    onOpenFile,
    onOpenFileToSide,
    onOpenDiff,
    projectRoot,
    activeFile,
    activeDiffFile,
    collapsed,
    onToggleCollapse,
    showSidebarToggle,
    appName,
    userEmail,
    workspaceName,
    workspaceId,
    onSwitchWorkspace,
    showSwitchWorkspace,
    onCreateWorkspace,
    onOpenUserSettings,
    onLogout,
    userMenuStatusMessage,
    userMenuStatusTone,
    onUserMenuRetry,
    userMenuDisabledActions,
  } = params
  const [creatingFile, setCreatingFile] = useState(false)
  const [viewMode, setViewMode] = useState('files') // 'files' | 'changes'
  const [searchExpanded, setSearchExpanded] = useState(false)

  const handleFileCreated = (path) => {
    setCreatingFile(false)
    if (path) {
      onOpenFile(path)
    }
  }

  const handleCancelCreate = () => {
    setCreatingFile(false)
  }

  if (collapsed) {
    return (
      <div className="panel-content filetree-panel filetree-collapsed">
        {showSidebarToggle && typeof onToggleCollapse === 'function' && (
          <Tooltip label="Expand sidebar">
            <button
              type="button"
              className="sidebar-toggle-btn"
              onClick={onToggleCollapse}
              aria-label="Expand sidebar"
            >
              <ChevronRight size={12} />
            </button>
          </Tooltip>
        )}
        <div className="filetree-collapsed-footer">
          <UserMenu
            email={userEmail}
            workspaceName={workspaceName}
            workspaceId={workspaceId}
            statusMessage={userMenuStatusMessage}
            statusTone={userMenuStatusTone}
            onRetry={onUserMenuRetry}
            disabledActions={userMenuDisabledActions}
            showSwitchWorkspace={showSwitchWorkspace}
            onSwitchWorkspace={onSwitchWorkspace}
            onCreateWorkspace={onCreateWorkspace}
            onOpenUserSettings={onOpenUserSettings}
            onLogout={onLogout}
            collapsed
          />
        </div>
      </div>
    )
  }

  return (
    <div className="panel-content filetree-panel">
      {showSidebarToggle && (
        <LeftPaneHeader
          onToggleSidebar={onToggleCollapse}
          appName={appName}
          viewMode={viewMode}
          onSetViewMode={setViewMode}
          searchExpanded={searchExpanded}
          onToggleSearch={() => setSearchExpanded((prev) => !prev)}
        />
      )}
      <div className="filetree-body">
        {viewMode === 'files' ? (
          <FileTree
            onOpen={onOpenFile}
            onOpenToSide={onOpenFileToSide}
            projectRoot={projectRoot}
            activeFile={activeFile}
            creatingFile={creatingFile}
            onFileCreated={handleFileCreated}
            onCancelCreate={handleCancelCreate}
            searchExpanded={searchExpanded}
          />
        ) : (
          <GitChangesView
            onOpenDiff={onOpenDiff}
            activeDiffFile={activeDiffFile}
          />
        )}
      </div>
      <div className="filetree-footer">
        <UserMenu
          email={userEmail}
          workspaceName={workspaceName}
          workspaceId={workspaceId}
          statusMessage={userMenuStatusMessage}
          statusTone={userMenuStatusTone}
          onRetry={onUserMenuRetry}
          disabledActions={userMenuDisabledActions}
          showSwitchWorkspace={showSwitchWorkspace}
          onSwitchWorkspace={onSwitchWorkspace}
          onCreateWorkspace={onCreateWorkspace}
          onOpenUserSettings={onOpenUserSettings}
          onLogout={onLogout}
        />
      </div>
    </div>
  )
}
