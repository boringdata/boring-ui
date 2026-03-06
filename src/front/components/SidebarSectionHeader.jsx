import { ChevronDown, ChevronRight, PanelLeftClose } from 'lucide-react'
import Tooltip from './Tooltip'

/**
 * LeftPaneHeader - Minimal header bar for the left sidebar with only the collapse toggle.
 * Rendered once by the first panel in the sidebar. Panel-specific controls
 * (search, view toggle) belong in each panel's own SidebarSectionHeader.
 */
export function LeftPaneHeader({ onToggleSidebar, appName }) {
  if (typeof onToggleSidebar !== 'function') return null
  return (
    <div className="left-pane-header left-pane-header-flat">
      <span className="left-pane-brand-title">{appName || 'workspace'}</span>
      <div className="left-pane-header-actions">
        <Tooltip label="Collapse sidebar">
          <button
            type="button"
            className="sidebar-toggle-btn"
            onClick={onToggleSidebar}
            aria-label="Collapse sidebar"
          >
            <PanelLeftClose size={14} />
          </button>
        </Tooltip>
      </div>
    </div>
  )
}

/**
 * SidebarSectionHeader - Section header for sub-components within the left sidebar.
 *
 * Renders:
 * - Section collapse toggle (chevron down/right) to vertically collapse the section
 * - Section title
 * - Optional right-side children (action buttons)
 *
 * Props:
 * - title: Section name (e.g., "Files", "Data Catalog")
 * - sectionCollapsed: Whether this section is vertically collapsed
 * - onToggleSection: Callback to toggle section collapse
 * - children: Optional action buttons rendered between title and spacer
 */
export default function SidebarSectionHeader({
  title,
  icon: Icon,
  sectionCollapsed = false,
  onToggleSection,
  children,
}) {
  return (
    <div className="sidebar-section-header">
      <Tooltip label={sectionCollapsed ? `Expand ${title}` : `Collapse ${title}`}>
        <button
          type="button"
          className="sidebar-section-toggle"
          onClick={onToggleSection}
          aria-label={sectionCollapsed ? `Expand ${title}` : `Collapse ${title}`}
        >
          {sectionCollapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
        </button>
      </Tooltip>
      {Icon && <span className="sidebar-section-icon"><Icon size={13} /></span>}
      <span className="sidebar-section-title">{title}</span>
      <div className="sidebar-section-actions">
        {children}
      </div>
    </div>
  )
}
