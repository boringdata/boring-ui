import { useContext } from 'react'
import PiNativeAdapter from '../providers/pi/nativeAdapter'
import PiBackendAdapter from '../providers/pi/backendAdapter'
import PiSessionToolbar from '../providers/pi/PiSessionToolbar'
import { getConfig, getDefaultConfig } from '../config'
import { CapabilitiesContext } from '../components/CapabilityGate'
import { getPiServiceUrl, isPiBackendMode } from '../providers/pi/config'
import AiChat from '../components/chat/AiChat'

function resolveAgentRuntime(params) {
  const config = getConfig() || getDefaultConfig()
  const configuredRuntime = String(
    params?.agentRuntime
      || config.agents?.default
      || config.agents?.runtime
      || config.agents?.available?.[0]
      || 'pi',
  ).trim().toLowerCase()

  return configuredRuntime === 'ai-sdk' ? 'ai-sdk' : 'pi'
}

export default function AgentPanel({ params }) {
  const capabilities = useContext(CapabilitiesContext)
  const {
    panelId,
    onSplitPanel,
    piSessionBootstrap = 'latest',
    piInitialSessionId = '',
  } = params || {}
  const agentRuntime = resolveAgentRuntime(params)
  const backendPi = agentRuntime === 'pi' && isPiBackendMode(capabilities)
  const piServiceUrl = getPiServiceUrl(capabilities)

  return (
    <div className="panel-content agent-panel-content" data-testid="agent-panel">
      <div className="agent-header">
        <div className="agent-header-spacer" />
        {agentRuntime === 'pi' ? (
          <PiSessionToolbar panelId={panelId} onSplitPanel={onSplitPanel} />
        ) : null}
      </div>
      <div className="agent-body">
        <div className="agent-instance active">
          {agentRuntime === 'ai-sdk' ? (
            <div className="provider-agent provider-ai-sdk" data-testid="agent-ai-sdk-app">
              <AiChat />
            </div>
          ) : backendPi ? (
            <div className="provider-agent provider-pi-backend" data-testid="agent-app">
              <PiBackendAdapter
                serviceUrl={piServiceUrl}
                panelId={panelId}
                sessionBootstrap={piSessionBootstrap}
              />
            </div>
          ) : (
            <div className="provider-agent provider-pi-native" data-testid="agent-app">
              <PiNativeAdapter
                panelId={panelId}
                sessionBootstrap={piSessionBootstrap}
                initialSessionId={piInitialSessionId}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
