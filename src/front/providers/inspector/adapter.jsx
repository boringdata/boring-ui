/**
 * Inspector chat provider adapter.
 *
 * Wraps the upstream sandbox-agent Inspector App component with
 * CSS scoping and theme bridge for boring-ui integration.
 * Injects direct-connect URL + token from useServiceConnection.
 */
import { ChevronRight } from 'lucide-react'
import InspectorApp from './upstream/App'
import { useServiceConnection } from '../../hooks/useServiceConnection'
import './upstream.css'
import './theme-bridge.css'

export default function InspectorAdapter({ onToggleCollapse }) {
  const { services } = useServiceConnection()
  const sandbox = services?.sandbox

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
            <InspectorApp
              initialEndpoint={sandbox?.url}
              initialToken={sandbox?.token}
            />
          </div>
        </div>
      </div>
    </>
  )
}
