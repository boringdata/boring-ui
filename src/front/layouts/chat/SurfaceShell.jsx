import React, { useState, useCallback, useMemo, useEffect, useRef } from 'react'
import { Database, FolderOpen, Layers, PanelLeftClose, PanelRightClose, Search, Sparkles, X } from 'lucide-react'

import FileTree from '../../shared/components/FileTree'
import Tooltip from '../../shared/components/Tooltip'
import { CollapsedSidebarActivityBar } from '../../shared/components/SidebarSectionHeader'
import { useFileSearch } from '../../shared/providers/data'
import { Button } from '../../shared/components/ui/button'
import { Input } from '../../shared/components/ui/input'
import SurfaceDockview from './SurfaceDockview'

const SURFACE_SIDEBAR_MIN_WIDTH = 240
const SURFACE_SIDEBAR_MAX_WIDTH = 420
const SURFACE_SIDEBAR_COLLAPSED_WIDTH = 56
const SURFACE_MAIN_MIN_WIDTH = 260

function clampSidebarWidth(nextWidth, surfaceWidth) {
  const availableWidth = Number.isFinite(surfaceWidth) ? surfaceWidth : 620
  const maxWidth = Math.max(
    SURFACE_SIDEBAR_MIN_WIDTH,
    Math.min(SURFACE_SIDEBAR_MAX_WIDTH, availableWidth - SURFACE_MAIN_MIN_WIDTH),
  )

  return Math.min(maxWidth, Math.max(SURFACE_SIDEBAR_MIN_WIDTH, Math.round(nextWidth)))
}

function FilteredResultsList({ results = [], emptyMessage, isFetching = false, renderItem }) {
  if (isFetching) {
    return <div className="sf-sidebar-scroll browse-drawer-empty">Searching...</div>
  }
  if (results.length === 0) {
    return <div className="sf-sidebar-scroll browse-drawer-empty">{emptyMessage}</div>
  }
  return (
    <div className="sf-sidebar-scroll sf-search-results" data-testid="surface-filtered-results">
      <div className="sf-search-list">
        {results.map(renderItem)}
      </div>
    </div>
  )
}

function DataCatalogList({
  entries = [],
  activeArtifactId = null,
  onSelectArtifact,
  emptyTestId = 'surface-data-catalog',
}) {
  if (entries.length === 0) {
    return (
      <div className="datacatalog-body sf-sidebar-scroll" data-testid={emptyTestId}>
        <div className="file-tree datacatalog-tree" role="tree" aria-label="Data Catalog">
          <div className="file-item datacatalog-item" role="treeitem">
            <span className="file-item-icon">
              <Database size={14} className="datacatalog-placeholder-icon" />
            </span>
            <span className="file-item-name">No data sources connected</span>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="datacatalog-body sf-sidebar-scroll" data-testid={emptyTestId}>
      <div className="file-tree datacatalog-tree" role="tree" aria-label="Data Catalog">
        {entries.map((entry) => (
          <button
            key={entry.id}
            type="button"
            role="treeitem"
            className={`file-item datacatalog-entry${entry.id === activeArtifactId ? ' active' : ''}`}
            onClick={() => onSelectArtifact?.(entry.id)}
          >
            <span className="file-item-icon">
              <Database size={14} />
            </span>
            <span className="file-item-content">
              <span className="file-item-name">{entry.title}</span>
              <span className="file-item-meta">{entry.subtitle}</span>
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}

export default function SurfaceShell({
  open = false,
  collapsed = false,
  width = 620,
  sidebarWidth = 296,
  artifacts = [],
  activeArtifact = null,
  activeArtifactId = null,
  onClose,
  onCollapse,
  onResize,
  onSidebarResize,
  layout = null,
  onLayoutChange,
  onSelectArtifact,
  onCloseArtifact,
  onOpenFile,
}) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [sidebarView, setSidebarView] = useState('files')
  const [searchQuery, setSearchQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const sidebarRef = useRef(null)
  const searchInputRef = useRef(null)

  useEffect(() => {
    const next = String(searchQuery || '').trim()
    const timer = window.setTimeout(() => setDebouncedQuery(next), 180)
    return () => window.clearTimeout(timer)
  }, [searchQuery])

  const { data: fileSearchResults = [], isFetching: isSearchingFiles } = useFileSearch(debouncedQuery, {
    enabled: Boolean(debouncedQuery),
  })

  const dataEntries = useMemo(
    () => artifacts
      .filter((artifact) => artifact && artifact.kind !== 'code')
      .map((artifact) => ({
        id: artifact.id,
        title: artifact.title || artifact.kind || 'Untitled',
        subtitle: [
          artifact.kind || 'artifact',
          artifact.params?.path || artifact.canonicalKey || '',
        ].filter(Boolean).join(' • '),
        searchText: [
          artifact.title,
          artifact.kind,
          artifact.canonicalKey,
          artifact.params?.path,
        ].filter(Boolean).join(' ').toLowerCase(),
      })),
    [artifacts],
  )

  const filteredDataEntries = useMemo(() => {
    const query = debouncedQuery.toLowerCase()
    if (!query) return dataEntries
    return dataEntries.filter((entry) => entry.searchText.includes(query))
  }, [dataEntries, debouncedQuery])

  const resolvedSidebarWidth = useMemo(
    () => (
      sidebarCollapsed
        ? SURFACE_SIDEBAR_COLLAPSED_WIDTH
        : clampSidebarWidth(sidebarWidth, width)
    ),
    [sidebarCollapsed, sidebarWidth, width],
  )

  const handleResizeMouseDown = useCallback(
    (event) => {
      event.preventDefault()
      const shell = document.querySelector('.surface-shell')
      const startX = event.clientX
      const startWidth = shell?.offsetWidth || width

      const onMove = (moveEvent) => {
        const nextWidth = Math.max(
          420,
          Math.min(window.innerWidth * 0.72, startWidth + (startX - moveEvent.clientX)),
        )
        onResize(nextWidth)
      }

      const onUp = () => {
        document.removeEventListener('mousemove', onMove)
        document.removeEventListener('mouseup', onUp)
        document.body.style.cursor = ''
        document.body.style.userSelect = ''
      }

      document.body.style.cursor = 'col-resize'
      document.body.style.userSelect = 'none'
      document.addEventListener('mousemove', onMove)
      document.addEventListener('mouseup', onUp)
    },
    [onResize, width],
  )

  const handleSidebarResizeMouseDown = useCallback((event) => {
    if (sidebarCollapsed || typeof onSidebarResize !== 'function') return

    event.preventDefault()
    const startX = event.clientX
    const startWidth = sidebarRef.current?.offsetWidth || resolvedSidebarWidth

    const onMove = (moveEvent) => {
      const nextWidth = clampSidebarWidth(startWidth + (moveEvent.clientX - startX), width)
      onSidebarResize(nextWidth)
    }

    const onUp = () => {
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }

    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }, [onSidebarResize, resolvedSidebarWidth, sidebarCollapsed, width])

  const handleSidebarResizeKeyDown = useCallback((event) => {
    if (sidebarCollapsed || typeof onSidebarResize !== 'function') return

    const step = event.shiftKey ? 32 : 16
    const minWidth = SURFACE_SIDEBAR_MIN_WIDTH
    const maxWidth = clampSidebarWidth(SURFACE_SIDEBAR_MAX_WIDTH, width)

    if (event.key === 'ArrowLeft') {
      event.preventDefault()
      onSidebarResize(clampSidebarWidth(resolvedSidebarWidth - step, width))
    }

    if (event.key === 'ArrowRight') {
      event.preventDefault()
      onSidebarResize(clampSidebarWidth(resolvedSidebarWidth + step, width))
    }

    if (event.key === 'Home') {
      event.preventDefault()
      onSidebarResize(minWidth)
    }

    if (event.key === 'End') {
      event.preventDefault()
      onSidebarResize(maxWidth)
    }
  }, [onSidebarResize, resolvedSidebarWidth, sidebarCollapsed, width])

  useEffect(() => {
    if (sidebarCollapsed || typeof onSidebarResize !== 'function') return
    const clampedWidth = clampSidebarWidth(sidebarWidth, width)
    if (clampedWidth !== sidebarWidth) {
      onSidebarResize(clampedWidth)
    }
  }, [onSidebarResize, sidebarCollapsed, sidebarWidth, width])

  const openFilesView = useCallback(() => {
    setSidebarCollapsed(false)
    setSidebarView('files')
    setSearchQuery('')
  }, [])

  const openDataView = useCallback(() => {
    setSidebarCollapsed(false)
    setSidebarView('data')
    setSearchQuery('')
  }, [])

  const focusSearch = useCallback(() => {
    setSidebarCollapsed(false)
    window.requestAnimationFrame(() => {
      searchInputRef.current?.focus()
      searchInputRef.current?.select?.()
    })
  }, [])

  const activityItems = [
    {
      id: 'files',
      label: 'Files',
      icon: FolderOpen,
      active: sidebarView === 'files',
      onClick: openFilesView,
    },
    {
      id: 'data-catalog',
      label: 'Data Catalog',
      icon: Database,
      active: sidebarView === 'data',
      onClick: openDataView,
    },
  ]

  const hasActiveQuery = debouncedQuery.length > 0
  const activeCatalogLabel = sidebarView === 'data' ? 'Data Catalog' : 'Files'
  const activeCatalogMeta = hasActiveQuery
    ? `${(sidebarView === 'data' ? filteredDataEntries : fileSearchResults).length} match${(sidebarView === 'data' ? filteredDataEntries : fileSearchResults).length === 1 ? '' : 'es'}`
    : (sidebarView === 'data'
      ? `${dataEntries.length} artifact${dataEntries.length === 1 ? '' : 's'}`
      : 'Browse project files')

  if (collapsed) {
    return (
      <button
        type="button"
        className="sf-handle"
        data-testid="surface-shell-handle"
        onClick={onCollapse}
        aria-label="Open Surface"
        title="Open Surface (⌘2)"
      >
        <Layers size={14} />
        {artifacts.length > 0 && (
          <span className="sf-handle-count" data-testid="surface-handle-count">
            {artifacts.length}
          </span>
        )}
      </button>
    )
  }

  const activeArtifactPath = activeArtifact?.params?.path || ''

  return (
    <div
      className="surface-shell"
      data-testid="surface-shell"
      style={{
        display: open ? 'flex' : 'none',
        width: `${width}px`,
      }}
    >
      <div className="sf-resize" onMouseDown={handleResizeMouseDown} />

      <aside
        ref={sidebarRef}
        className={`sf-sidebar${sidebarCollapsed ? ' collapsed' : ''}`}
        data-testid="surface-sidebar"
        style={{
          width: `${resolvedSidebarWidth}px`,
          minWidth: `${resolvedSidebarWidth}px`,
          flexBasis: `${resolvedSidebarWidth}px`,
        }}
      >
        {sidebarCollapsed ? (
          <div className="panel-content filetree-panel filetree-collapsed sf-sidebar-collapsed">
            <CollapsedSidebarActivityBar
              onExpandSidebar={() => setSidebarCollapsed(false)}
              items={activityItems}
            />
          </div>
        ) : (
          <div className={`panel-content sf-sidebar-panel-shell ${sidebarView === 'data' ? 'datacatalog-panel' : 'filetree-panel'}`}>
            <div className="sf-sidebar-top">
              <div className="left-pane-header left-pane-header-flat sf-sidebar-head">
                <div className="sf-sidebar-head-copy">
                  <div className="sf-sidebar-head-eyebrow">Workbench</div>
                  <div className="sf-sidebar-head-title">{activeCatalogLabel}</div>
                  <div className="sf-sidebar-head-meta">{activeCatalogMeta}</div>
                </div>
                <div className="left-pane-header-actions sf-sidebar-head-actions">
                  <div className="sf-sidebar-mode-switch" role="tablist" aria-label="Workbench catalogs">
                    <Tooltip label="Files">
                      <button
                        type="button"
                        role="tab"
                        aria-label="Files"
                        aria-selected={sidebarView === 'files'}
                        className={`sidebar-action-btn sf-sidebar-mode-tab${sidebarView === 'files' ? ' active' : ''}`}
                        onClick={openFilesView}
                      >
                        <FolderOpen size={14} />
                      </button>
                    </Tooltip>
                    <Tooltip label="Data Catalog">
                      <button
                        type="button"
                        role="tab"
                        aria-label="Data Catalog"
                        aria-selected={sidebarView === 'data'}
                        className={`sidebar-action-btn sf-sidebar-mode-tab${sidebarView === 'data' ? ' active' : ''}`}
                        onClick={openDataView}
                      >
                        <Database size={14} />
                      </button>
                    </Tooltip>
                  </div>

                  <Tooltip label="Collapse sidebar">
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="sidebar-toggle-btn"
                      onClick={() => setSidebarCollapsed(true)}
                      aria-label="Collapse sidebar"
                    >
                      <PanelLeftClose size={14} />
                    </Button>
                  </Tooltip>
                </div>
              </div>

              <div className="sf-sidebar-search">
                <Search size={14} className="sf-sidebar-search-icon" />
                <Input
                  ref={searchInputRef}
                  aria-label="Search files and data catalog"
                  className="sf-sidebar-search-input"
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder={sidebarView === 'data' ? 'Filter data catalog...' : 'Filter files...'}
                />
                {searchQuery ? (
                  <button
                    type="button"
                    className="sf-sidebar-search-clear"
                    onClick={() => setSearchQuery('')}
                    aria-label="Clear search"
                  >
                    <X size={14} />
                  </button>
                ) : null}
              </div>
            </div>

            <div className="sf-sidebar-body">
              {sidebarView === 'data' ? (
                hasActiveQuery ? (
                  <FilteredResultsList
                    results={filteredDataEntries}
                    emptyMessage="No matching data sources"
                    isFetching={false}
                    renderItem={(entry) => (
                      <button
                        key={entry.id}
                        type="button"
                        className="sf-search-row"
                        onClick={() => onSelectArtifact?.(entry.id)}
                      >
                        <span className="sf-search-row-icon"><Database size={14} /></span>
                        <span className="sf-search-row-copy">
                          <span className="sf-search-row-title">{entry.title}</span>
                          <span className="sf-search-row-subtitle">{entry.subtitle}</span>
                        </span>
                      </button>
                    )}
                  />
                ) : (
                  <DataCatalogList
                    entries={dataEntries}
                    activeArtifactId={activeArtifactId}
                    onSelectArtifact={onSelectArtifact}
                  />
                )
              ) : (
                hasActiveQuery ? (
                  <FilteredResultsList
                    results={Array.isArray(fileSearchResults) ? fileSearchResults : []}
                    emptyMessage="No matching files"
                    isFetching={isSearchingFiles}
                    renderItem={(result) => (
                      <button
                        key={`${result.path}-${result.line_number || 0}`}
                        type="button"
                        className="sf-search-row"
                        onClick={() => onOpenFile?.(result.path)}
                      >
                        <span className="sf-search-row-icon"><FolderOpen size={14} /></span>
                        <span className="sf-search-row-copy">
                          <span className="sf-search-row-title">{result.path}</span>
                          <span className="sf-search-row-subtitle">
                            {result.line_number ? `Line ${result.line_number}` : 'File'}
                            {result.line ? ` · ${String(result.line).trim()}` : ''}
                          </span>
                        </span>
                      </button>
                    )}
                  />
                ) : (
                  <div className="filetree-body sf-sidebar-scroll">
                    <FileTree
                      onOpen={onOpenFile}
                      activeFile={activeArtifactPath}
                      searchExpanded={false}
                    />
                  </div>
                )
              )}
            </div>

          </div>
        )}
      </aside>

      {!sidebarCollapsed ? (
        <div
          className="sf-sidebar-resize"
          data-testid="surface-sidebar-resize"
          role="separator"
          aria-label="Resize workbench sidebar"
          aria-orientation="vertical"
          aria-valuemin={SURFACE_SIDEBAR_MIN_WIDTH}
          aria-valuemax={clampSidebarWidth(SURFACE_SIDEBAR_MAX_WIDTH, width)}
          aria-valuenow={resolvedSidebarWidth}
          tabIndex={0}
          onMouseDown={handleSidebarResizeMouseDown}
          onKeyDown={handleSidebarResizeKeyDown}
        />
      ) : null}

      <div className="sf-main">
        <button
          className="sf-floating-close"
          data-testid="surface-close"
          onClick={onClose}
          title="Close Surface"
          type="button"
        >
          <PanelRightClose size={14} />
        </button>

        <div className="sf-body">
          {artifacts.length === 0 ? (
            <div className="sf-empty">
              <div className="sf-empty-icon">
                <Sparkles size={20} />
              </div>
              <div className="sf-empty-title">Open files and artifacts here</div>
              <div className="sf-empty-sub">
                Use the file tree to open code, or ask the agent to create artifacts in the
                workbench.
              </div>
            </div>
          ) : (
            <SurfaceDockview
              artifacts={artifacts}
              activeArtifactId={activeArtifactId}
              onSelectArtifact={onSelectArtifact}
              onCloseArtifact={onCloseArtifact}
              layout={layout}
              onLayoutChange={onLayoutChange}
            />
          )}
        </div>
      </div>
    </div>
  )
}
