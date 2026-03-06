import { ChevronRight, Database } from 'lucide-react'
import SidebarSectionHeader, { LeftPaneHeader } from '../components/SidebarSectionHeader'
import Tooltip from '../components/Tooltip'

export default function DataCatalogPanel({ params }) {
  const {
    collapsed,
    onToggleCollapse,
    showSidebarToggle,
    appName,
    sectionCollapsed,
    onToggleSection,
  } = params

  if (collapsed) {
    return (
      <div className="panel-content datacatalog-panel">
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
      </div>
    )
  }

  return (
    <div className="panel-content datacatalog-panel">
      {showSidebarToggle && (
        <LeftPaneHeader onToggleSidebar={onToggleCollapse} appName={appName} />
      )}
      <SidebarSectionHeader
        title="Data Catalog"
        icon={Database}
        sectionCollapsed={sectionCollapsed}
        onToggleSection={onToggleSection}
      />
      {!sectionCollapsed && (
        <div className="datacatalog-body">
          <div className="file-tree datacatalog-tree" role="tree" aria-label="Data Catalog">
            <div className="file-item datacatalog-item" role="treeitem">
              <span className="file-item-icon">
                <Database size={14} className="datacatalog-placeholder-icon" />
              </span>
              <span className="file-item-name">No data sources connected</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
