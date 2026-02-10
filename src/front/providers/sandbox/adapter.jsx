/**
 * Sandbox chat provider adapter.
 *
 * Uses useServiceConnection to get direct-connect URL + token,
 * falling back to the boring-ui proxy when not available.
 * Passes fetchWithRetry for transparent 401 auto-retry.
 */
import { useCallback } from 'react'
import { ChevronRight } from 'lucide-react'
import SandboxChat from '../../components/chat/SandboxChat'
import { useServiceConnection } from '../../hooks/useServiceConnection'

export default function SandboxAdapter({ onToggleCollapse }) {
  const { services, fetchWithRetry } = useServiceConnection()
  const sandbox = services?.sandbox

  // Bind fetchWithRetry to the sandbox service for SandboxChat
  const sandboxFetch = useCallback(
    (url, init) => fetchWithRetry('sandbox', url, init),
    [fetchWithRetry],
  )

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
        <span className="terminal-title-text">Sandbox</span>
        <div className="terminal-header-spacer" />
      </div>
      <div className="terminal-body">
        <div className="terminal-instance active">
          <SandboxChat
            baseUrl={sandbox?.url}
            authToken={sandbox?.token}
            authFetch={sandboxFetch}
          />
        </div>
      </div>
    </>
  )
}
