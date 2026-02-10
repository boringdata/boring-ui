/**
 * Sandbox chat provider adapter.
 *
 * Wraps the existing SandboxChat component.
 */
import { ChevronRight } from 'lucide-react'
import SandboxChat from '../../components/chat/SandboxChat'

export default function SandboxAdapter({ onToggleCollapse }) {
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
          <SandboxChat />
        </div>
      </div>
    </>
  )
}
