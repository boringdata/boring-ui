import { useMemo } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useCapabilitiesContext } from '../components/CapabilityGate'
import { setCompanionConfig } from '../providers/companion/config'
import CompanionAdapter from '../providers/companion/adapter'
import EmbeddedSessionToolbar from '../providers/companion/EmbeddedSessionToolbar'
import PiNativeAdapter from '../providers/pi/nativeAdapter'
import PiBackendAdapter from '../providers/pi/backendAdapter'
import PiSessionToolbar from '../providers/pi/PiSessionToolbar'
import { getPiServiceUrl, isPiBackendMode } from '../providers/pi/config'
import '../providers/companion/upstream.css'
import '../providers/companion/theme-bridge.css'

export default function CompanionPanel({ params }) {
  const { collapsed, onToggleCollapse, provider } = params || {}
  const capabilities = useCapabilitiesContext()
  const activeProvider = provider === 'all' ? 'all' : provider === 'pi' ? 'pi' : 'companion'
  const companionUrl = capabilities?.services?.companion?.url
  const piBackendEnabled = activeProvider === 'pi' && isPiBackendMode(capabilities)
  const piBackendEnabledForAll = activeProvider === 'all' && isPiBackendMode(capabilities)
  const piServiceUrl = piBackendEnabled ? getPiServiceUrl(capabilities) : ''
  const piServiceUrlForAll = piBackendEnabledForAll ? getPiServiceUrl(capabilities) : ''

  const companionReady = useMemo(() => {
    if (companionUrl) {
      setCompanionConfig(companionUrl, '')
      return true
    }

    return false
  }, [companionUrl])

  const ready = useMemo(() => {
    if (activeProvider === 'pi') return true
    if (activeProvider === 'all') return companionReady
    return companionReady
  }, [activeProvider, companionReady])

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
        <div className="sidebar-collapsed-label">{activeProvider === 'all' ? 'Agents' : 'Agent'}</div>
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
        <span className="terminal-title-text">{activeProvider === 'all' ? 'Agents' : 'Agent'}</span>
        <div className="terminal-header-spacer" />
        {activeProvider === 'all'
          ? null
          : activeProvider === 'pi'
            ? <PiSessionToolbar />
            : <EmbeddedSessionToolbar />}
      </div>
      <div className="terminal-body companion-body">
        {activeProvider === 'all' ? (
          <div
            className="companion-instance active"
            style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, height: '100%', minHeight: 0, padding: 8 }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0, border: '1px solid var(--color-border)' }}>
              <div className="terminal-header" style={{ minHeight: 32 }}>
                <span className="terminal-title-text">Companion</span>
                <div className="terminal-header-spacer" />
                <EmbeddedSessionToolbar />
              </div>
              <div style={{ flex: 1, minHeight: 0 }}>
                {companionReady ? (
                  <div className="provider-companion" data-testid="companion-app">
                    <CompanionAdapter />
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

            <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0, border: '1px solid var(--color-border)' }}>
              <div className="terminal-header" style={{ minHeight: 32 }}>
                <span className="terminal-title-text">PI</span>
                <div className="terminal-header-spacer" />
                <PiSessionToolbar />
              </div>
              <div style={{ flex: 1, minHeight: 0 }}>
                <div className="provider-companion provider-pi-native" data-testid="pi-app">
                  {piBackendEnabledForAll
                    ? <PiBackendAdapter serviceUrl={piServiceUrlForAll} />
                    : <PiNativeAdapter />}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="companion-instance active">
            {ready ? (
              activeProvider === 'pi'
                ? (
                  <div className="provider-companion provider-pi-native" data-testid="pi-app">
                    {piBackendEnabled
                      ? <PiBackendAdapter serviceUrl={piServiceUrl} />
                      : <PiNativeAdapter />}
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
        )}
      </div>
    </div>
  )
}
