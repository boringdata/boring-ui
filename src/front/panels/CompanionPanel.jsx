import { useMemo } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useCapabilitiesContext } from '../components/CapabilityGate'
import { setCompanionConfig } from '../providers/companion/config'
import CompanionAdapter from '../providers/companion/adapter'
import EmbeddedSessionToolbar from '../providers/companion/EmbeddedSessionToolbar'
import PiNativeAdapter from '../providers/pi/nativeAdapter'
import PiSessionToolbar from '../providers/pi/PiSessionToolbar'
import '../providers/companion/upstream.css'
import '../providers/companion/theme-bridge.css'

export default function CompanionPanel({ params }) {
  const { collapsed, onToggleCollapse, provider } = params || {}
  const capabilities = useCapabilitiesContext()
  const activeProvider = provider === 'pi' ? 'pi' : 'companion'
  const companionUrl = capabilities?.services?.companion?.url
  const piUrl = capabilities?.services?.pi?.url

  const ready = useMemo(() => {
    if (activeProvider === 'pi') {
      return true
    }

    if (companionUrl) {
      setCompanionConfig(companionUrl, '')
      return true
    }

    return false
  }, [activeProvider, companionUrl])

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
        {activeProvider === 'pi' ? <PiSessionToolbar /> : <EmbeddedSessionToolbar />}
      </div>
      <div className="terminal-body companion-body">
        <div className="companion-instance active">
          {ready ? (
            activeProvider === 'pi'
              ? (
                <div className="provider-companion provider-pi-native" data-testid="pi-app" data-service-url={piUrl || ''}>
                  <PiNativeAdapter />
                </div>
                )
              : (
                <div className="provider-companion" data-testid="companion-app">
                  <CompanionAdapter />
                </div>
                )
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
