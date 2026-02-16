import { useMemo } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useCapabilitiesContext } from '../components/CapabilityGate'
import { setCompanionConfig } from '../providers/companion/config'
import CompanionAdapter from '../providers/companion/adapter'
import PiAdapter from '../providers/pi/adapter'
import EmbeddedSessionToolbar from '../providers/companion/EmbeddedSessionToolbar'
import '../providers/companion/upstream.css'
import '../providers/companion/theme-bridge.css'

export default function CompanionPanel({ params }) {
  const { collapsed, onToggleCollapse, provider } = params || {}
  const capabilities = useCapabilitiesContext()
  const activeProvider = provider === 'pi' ? 'pi' : 'companion'
  const companionUrl = capabilities?.services?.companion?.url
  const piUrl = capabilities?.services?.pi?.url
  const agentUrl = activeProvider === 'pi' ? piUrl : companionUrl

  // Set config synchronously before CompanionApp renders.
  // useMemo runs during render, before children mount.
  const ready = useMemo(() => {
    if (activeProvider === 'companion' && companionUrl) {
      setCompanionConfig(companionUrl, '')
      return true
    }
    if (activeProvider === 'pi' && piUrl) return true
    return false
  }, [activeProvider, companionUrl, piUrl])

  if (collapsed) {
    return (
      <div
        className="panel-content terminal-panel-content right-rail-panel companion-panel-content terminal-collapsed"
        data-testid="companion-panel-collapsed"
      >
        <button
          type="button"
          className="sidebar-toggle-btn"
          onClick={onToggleCollapse}
          title="Expand agent panel"
          aria-label="Expand agent panel"
        >
          <ChevronLeft size={16} />
        </button>
        <div className="sidebar-collapsed-label">Agent</div>
      </div>
    )
  }

  return (
    <div className="panel-content terminal-panel-content right-rail-panel companion-panel-content" data-testid="companion-panel">
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
        <span className="terminal-title-text">Agent</span>
        <div className="terminal-header-spacer" />
        {activeProvider === 'companion' ? <EmbeddedSessionToolbar /> : null}
      </div>
      <div className="terminal-body companion-body">
        <div className="companion-instance active">
          {ready ? (
            activeProvider === 'companion'
              ? (
                <div className="provider-companion" data-testid="companion-app">
                  <CompanionAdapter />
                </div>
                )
              : (
                <div className="provider-pi" data-testid="pi-app">
                  <PiAdapter url={agentUrl} />
                </div>
                )
          ) : (
            <div
              data-testid="companion-connecting"
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--color-text-tertiary)' }}
            >
              {activeProvider === 'pi' ? 'Connecting to Pi server...' : 'Connecting to Companion server...'}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
