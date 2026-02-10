/**
 * Sandbox chat provider adapter.
 *
 * Uses useServiceConnection to get direct-connect URL + token,
 * falling back to the boring-ui proxy when not available.
 */
import { ChevronRight } from 'lucide-react'
import SandboxChat from '../../components/chat/SandboxChat'
import { useServiceConnection } from '../../hooks/useServiceConnection'

export default function SandboxAdapter({ onToggleCollapse }) {
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
        <span className="terminal-title-text">Sandbox</span>
        <div className="terminal-header-spacer" />
      </div>
      <div className="terminal-body">
        <div className="terminal-instance active">
          <SandboxChat
            baseUrl={sandbox?.url}
            authToken={sandbox?.token}
          />
        </div>
      </div>
    </>
  )
}
