import React, { useState, useCallback, useEffect } from 'react'
import {
  PanelRightOpen,
  PanelRightClose,
  FolderOpen,
  Folder,
  ChevronDown,
  ChevronRight,
  X,
  Sparkles,
  FileCode,
  Database,
  Layers,
} from 'lucide-react'
import SurfaceDockview from './SurfaceDockview'

/**
 * ExplorerSection — collapsible section in the explorer sidebar.
 */
function ExplorerSection({ title, icon, count, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="sf-explorer-group">
      <div className="sf-explorer-cat" onClick={() => setOpen(o => !o)} style={{ cursor: 'pointer' }}>
        {open ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
        {icon}
        {title}
        {count != null && <span>{count}</span>}
      </div>
      {open && children}
    </div>
  )
}

/**
 * ExplorerFileTree — browse workspace files inside the Surface explorer.
 */
function ExplorerFileTree({ onOpenFile }) {
  const [entries, setEntries] = useState([])
  const [currentPath, setCurrentPath] = useState('.')

  const loadDir = useCallback((dirPath) => {
    fetch(`/api/tree?path=${encodeURIComponent(dirPath)}`)
      .then(r => r.json())
      .then(data => { setEntries(data); setCurrentPath(dirPath) })
      .catch(() => setEntries([]))
  }, [])

  useEffect(() => { loadDir('.') }, [loadDir])

  return (
    <div className="sf-explorer-filetree">
      {currentPath !== '.' && (
        <div className="sf-explorer-item" onClick={() => loadDir(currentPath.split('/').slice(0, -1).join('/') || '.')}>
          <span className="sf-explorer-item-icon" style={{ opacity: 0.5 }}>..</span>
          <span className="sf-explorer-item-title" style={{ opacity: 0.5 }}>..</span>
        </div>
      )}
      {entries.map(e => (
        <div key={e.path}
          className="sf-explorer-item"
          onClick={() => e.is_dir ? loadDir(e.path) : onOpenFile?.(e.path)}>
          <span className="sf-explorer-item-icon">
            {e.is_dir ? <Folder size={13} style={{ color: '#f59e0b' }} /> : <FileCode size={13} style={{ color: '#a78bfa' }} />}
          </span>
          <span className="sf-explorer-item-title">{e.name}</span>
          {e.is_dir && <ChevronRight size={10} style={{ marginLeft: 'auto', opacity: 0.3 }} />}
        </div>
      ))}
      {entries.length === 0 && <div className="sf-explorer-empty">Empty</div>}
    </div>
  )
}

/**
 * SurfaceShell - Floating island container for artifacts.
 *
 * When `open` is false: display: none (NOT unmounted) -- preserves state.
 * When `collapsed`: shows 36px handle strip with artifact count.
 * When open: shows floating island with explorer sidebar + Dockview viewer.
 */
export default function SurfaceShell({
  open = false,
  collapsed = false,
  width = 620,
  artifacts = [],
  activeArtifactId = null,
  onClose,
  onCollapse,
  onResize,
  onSelectArtifact,
  onCloseArtifact,
  onOpenFile,
}) {
  const [explorerOpen, setExplorerOpen] = useState(true)

  const handleResizeMouseDown = useCallback(
    (e) => {
      e.preventDefault()
      const sf = document.querySelector('.surface-shell')
      const startX = e.clientX
      const startW = sf?.offsetWidth || width
      const onMove = (ev) => {
        const newWidth = Math.max(380, Math.min(window.innerWidth * 0.65, startW + (startX - ev.clientX)))
        onResize(newWidth)
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
    [width, onResize]
  )

  // Collapsed handle — always visible, shows Layers icon + artifact count
  if (collapsed) {
    return (
      <div
        className="sf-handle"
        data-testid="surface-shell-handle"
        onClick={onCollapse}
        title="Open Surface (⌘2)"
      >
        <Layers size={14} />
        {artifacts.length > 0 && (
          <span className="sf-handle-count" data-testid="surface-handle-count">
            {artifacts.length}
          </span>
        )}
      </div>
    )
  }

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

      {/* Explorer sidebar — artifact browser: open tabs + file tree + data */}
      <div className={`sf-explorer${explorerOpen ? '' : ' closed'}`}>
        <div className="sf-explorer-head">
          <span>Artifacts</span>
        </div>
        <div className="sf-explorer-list">
          {/* Section: Open artifacts */}
          {artifacts.length > 0 && (
            <ExplorerSection title="Open" count={artifacts.length} defaultOpen>
              {artifacts.map(a => (
                <div key={a.id}
                  className={`sf-explorer-item${a.id === activeArtifactId ? ' active' : ''}`}
                  onClick={() => onSelectArtifact(a.id)}>
                  <span className="sf-explorer-item-icon"><FileCode size={13} style={{ color: '#a78bfa' }} /></span>
                  <span className="sf-explorer-item-title">{a.title}</span>
                  {a.id === activeArtifactId && <span className="sf-explorer-item-dot" />}
                </div>
              ))}
            </ExplorerSection>
          )}

          {/* Section: Files — browseable workspace file tree */}
          <ExplorerSection title="Files" icon={<FolderOpen size={11} />} defaultOpen>
            <ExplorerFileTree onOpenFile={onOpenFile} />
          </ExplorerSection>

          {/* Section: Data — catalog entries */}
          <ExplorerSection title="Data" icon={<Database size={11} />}>
            <div className="sf-explorer-empty">No data sources</div>
          </ExplorerSection>
        </div>
      </div>

      <div className="sf-main">
        {/* Top bar: explorer toggle + tabs + close */}
        <div className="sf-topbar">
          <button
            className={`sf-explorer-toggle${explorerOpen ? ' active' : ''}`}
            onClick={() => setExplorerOpen((o) => !o)}
          >
            {explorerOpen ? (
              <ChevronDown size={12} style={{ transform: 'rotate(90deg)' }} />
            ) : (
              <ChevronRight size={12} />
            )}
            <FolderOpen size={13} />
            <span>Artifacts</span>
            {artifacts.length > 0 && (
              <span className="sf-explorer-toggle-count">{artifacts.length}</span>
            )}
          </button>

          <div className="sf-tabs">
            {artifacts.map((artifact) => (
              <button
                key={artifact.id}
                className={`sf-tab${artifact.id === activeArtifactId ? ' active' : ''}`}
                data-testid={`surface-tab-${artifact.id}`}
                onClick={() => onSelectArtifact(artifact.id)}
              >
                <span>{artifact.title}</span>
                <span
                  className="sf-tab-close"
                  onClick={(e) => {
                    e.stopPropagation()
                    onCloseArtifact(artifact.id)
                  }}
                >
                  <X size={10} />
                </span>
              </button>
            ))}
          </div>

          <div style={{ flex: 1 }} />

          <button
            className="sf-viewer-btn"
            data-testid="surface-close"
            onClick={onClose}
            title="Close Surface"
          >
            <PanelRightClose size={14} />
          </button>
        </div>

        {/* Viewer content — Dockview for drag/split tabs */}
        <div className="sf-body">
          {artifacts.length === 0 ? (
            <div className="sf-empty">
              <div className="sf-empty-icon">
                <Sparkles size={20} />
              </div>
              <div className="sf-empty-title">Select an artifact</div>
              <div className="sf-empty-sub">
                Browse files in the explorer, or ask the agent to analyze data,
                generate charts, review documents, or write code.
              </div>
            </div>
          ) : (
            <SurfaceDockview
              artifacts={artifacts}
              activeArtifactId={activeArtifactId}
              onSelectArtifact={onSelectArtifact}
              onCloseArtifact={onCloseArtifact}
            />
          )}
        </div>
      </div>
    </div>
  )
}
