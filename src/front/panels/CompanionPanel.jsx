import { useMemo } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useCapabilitiesContext } from '../components/CapabilityGate'
import { setCompanionConfig } from '../providers/companion/config'
import CompanionApp from '../providers/companion/upstream/App'
import '../providers/companion/upstream.css'
import '../providers/companion/theme-bridge.css'

export default function CompanionPanel({ params }) {
  const { collapsed, onToggleCollapse } = params || {}
  const capabilities = useCapabilitiesContext()
  const companionUrl = capabilities?.services?.companion?.url

  // Set config synchronously before CompanionApp renders.
  // useMemo runs during render, before children mount.
  const ready = useMemo(() => {
    if (companionUrl) {
      setCompanionConfig(companionUrl, '')
      return true
    }
    return false
  }, [companionUrl])

  if (collapsed) {
    return (
      <div
        className="panel-content terminal-panel-content terminal-collapsed"
        data-testid="companion-panel-collapsed"
      >
        <button
          type="button"
          className="sidebar-toggle-btn"
          onClick={onToggleCollapse}
          title="Expand companion panel"
          aria-label="Expand companion panel"
        >
          <ChevronLeft size={16} />
        </button>
        <div className="sidebar-collapsed-label">Companion</div>
      </div>
    )
  }

  return (
    <div className="panel-content terminal-panel-content" data-testid="companion-panel">
      <div className="terminal-header">
        <button
          type="button"
          className="sidebar-toggle-btn"
          onClick={onToggleCollapse}
          title="Collapse companion panel"
          aria-label="Collapse companion panel"
        >
          <ChevronRight size={16} />
        </button>
        <span className="terminal-title-text">Companion</span>
        <div className="terminal-header-spacer" />
      </div>
      <div className="terminal-body">
        <div className="terminal-instance active">
          {ready ? (
            <div className="provider-companion" data-testid="companion-app">
              <CompanionApp />
            </div>
          ) : (
            <div
              data-testid="companion-connecting"
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--color-text-tertiary)' }}
            >
              Connecting to Companion server...
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
