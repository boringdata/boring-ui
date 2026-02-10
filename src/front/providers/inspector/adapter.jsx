/**
 * Inspector chat provider adapter.
 *
 * Wraps the upstream sandbox-agent Inspector App component with
 * CSS scoping and theme bridge for boring-ui integration.
 */
import { ChevronRight } from 'lucide-react'
import InspectorApp from './upstream/App'
import './upstream.css'
import './theme-bridge.css'

export default function InspectorAdapter({ onToggleCollapse }) {
  return (
    <>
      <div className="terminal-header">
        <button
          type="button"
          className="sidebar-toggle-btn"
          onClick={onToggleCollapse}
          title="Collapse agent panel"
          aria-label="Collapse agent panel"
        >
          <ChevronRight size={16} />
        </button>
        <span className="terminal-title-text">Inspector</span>
        <div className="terminal-header-spacer" />
      </div>
      <div className="terminal-body">
        <div className="terminal-instance active">
          <div className="provider-inspector">
            <InspectorApp />
          </div>
        </div>
      </div>
    </>
  )
}
