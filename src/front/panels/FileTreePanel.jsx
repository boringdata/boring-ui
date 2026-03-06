import React, { useState } from 'react'
import { ChevronRight, FolderOpen, GitBranch, Search } from 'lucide-react'
import FileTree from '../components/FileTree'
import GitChangesView from '../components/GitChangesView'
import UserMenu from '../components/UserMenu'
import Tooltip from '../components/Tooltip'
import SidebarSectionHeader, { LeftPaneHeader } from '../components/SidebarSectionHeader'

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
    sectionCollapsed,
    onToggleSection,
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
    <div className={`panel-content filetree-panel${sectionCollapsed ? ' filetree-section-collapsed' : ''}`}>
      {showSidebarToggle && (
        <LeftPaneHeader onToggleSidebar={onToggleCollapse} appName={appName} />
      )}
      {sectionCollapsed && <div className="filetree-section-spacer" />}
      <SidebarSectionHeader
        title="Files"
        icon={FolderOpen}
        sectionCollapsed={sectionCollapsed}
        onToggleSection={onToggleSection}
      >
        {!sectionCollapsed && (
          <>
            <div className="sidebar-view-toggle" role="tablist" aria-label="Sidebar view mode">
              <Tooltip label="File tree">
                <button
                  type="button"
                  className={`view-toggle-btn ${viewMode === 'files' ? 'active' : ''}`}
                  onClick={() => setViewMode('files')}
                  aria-label="File tree view"
                  role="tab"
                  aria-selected={viewMode === 'files'}
                >
                  <FolderOpen size={14} />
                </button>
              </Tooltip>
              <Tooltip label="Git changes">
                <button
                  type="button"
                  className={`view-toggle-btn ${viewMode === 'changes' ? 'active' : ''}`}
                  onClick={() => setViewMode('changes')}
                  aria-label="Git changes view"
                  role="tab"
                  aria-selected={viewMode === 'changes'}
                >
                  <GitBranch size={14} />
                </button>
              </Tooltip>
            </div>
            <Tooltip
              label={searchExpanded ? 'Hide search' : 'Search files'}
              shortcut="Ctrl+P"
            >
              <button
                type="button"
                className={`sidebar-action-btn ${searchExpanded ? 'active' : ''}`}
                onClick={() => setSearchExpanded((prev) => !prev)}
                aria-label={searchExpanded ? 'Hide search' : 'Search files'}
              >
                <Search size={13} />
              </button>
            </Tooltip>
          </>
        )}
      </SidebarSectionHeader>
      {!sectionCollapsed && (
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
      )}
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
