/**
 * Companion chat provider adapter.
 *
 * Wraps the upstream Companion App component with CSS scoping,
 * theme bridge, and Direct Connect configuration.
 * Sets base URL + auth token synchronously before mounting the upstream App.
 */
import { useMemo } from 'react'
import { ChevronRight } from 'lucide-react'
import CompanionApp from './upstream/App'
import { useServiceConnection } from '../../hooks/useServiceConnection'
import { setCompanionConfig } from './config'
import { ToolRendererProvider } from '../../shared/renderers'
import './upstream.css'
import './theme-bridge.css'

export default function CompanionAdapter({ onToggleCollapse }) {
  const { services } = useServiceConnection()
  const companion = services?.companion

  // Configure upstream modules synchronously before CompanionApp renders.
  // useMemo runs during render (before children mount), avoiding the race
  // condition where useEffect would fire after the first child render.
  const ready = useMemo(() => {
    if (companion?.url) {
      setCompanionConfig(companion.url, companion.token)
      return true
    }
    return false
  }, [companion?.url, companion?.token])

  const header = (
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
  )

  if (!ready) {
    return (
      <>
        {header}
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
      {header}
      <div className="terminal-body">
        <div className="terminal-instance active">
          <div className="provider-companion">
            <ToolRendererProvider>
              <CompanionApp />
            </ToolRendererProvider>
          </div>
        </div>
      </div>
    </>
  )
}
