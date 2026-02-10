/**
 * Companion chat provider adapter.
 *
 * Wraps the upstream Companion App component with CSS scoping,
 * theme bridge, and Direct Connect configuration.
 * Sets base URL + auth token before mounting the upstream App.
 */
import { useEffect, useRef } from 'react'
import { ChevronRight } from 'lucide-react'
import CompanionApp from './upstream/App'
import { useServiceConnection } from '../../hooks/useServiceConnection'
import { setCompanionConfig } from './config'
import './upstream.css'
import './theme-bridge.css'

export default function CompanionAdapter({ onToggleCollapse }) {
  const { services } = useServiceConnection()
  const companion = services?.companion
  const configured = useRef(false)

  // Configure upstream modules before first render
  useEffect(() => {
    if (companion?.url) {
      setCompanionConfig(companion.url, companion.token)
      configured.current = true
    }
  }, [companion?.url, companion?.token])

  // Don't render until we have connection info
  if (!companion?.url) {
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
          <span className="terminal-title-text">Companion</span>
          <div className="terminal-header-spacer" />
        </div>
        <div className="terminal-body">
          <div className="terminal-instance active" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-text-tertiary)' }}>
            Connecting to Companion server...
          </div>
        </div>
      </>
    )
  }

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
        <span className="terminal-title-text">Companion</span>
        <div className="terminal-header-spacer" />
      </div>
      <div className="terminal-body">
        <div className="terminal-instance active">
          <div className="provider-companion">
            <CompanionApp />
          </div>
        </div>
      </div>
    </>
  )
}
