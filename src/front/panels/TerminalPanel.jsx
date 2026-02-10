import { ChevronLeft } from 'lucide-react'
import { useConfig } from '../config'
import chatProviders from '../providers'

export default function TerminalPanel({ params }) {
  const { collapsed, onToggleCollapse, approvals, onFocusReview, onDecision, normalizeApprovalPath } = params || {}
  const config = useConfig()
  const chatProvider = config.chat?.provider || 'claude'

  if (collapsed) {
    return (
      <div className="panel-content terminal-panel-content terminal-collapsed">
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

  const provider = chatProviders.get(chatProvider)
  if (!provider) {
    return (
      <div className="panel-content terminal-panel-content">
        <div className="terminal-header">
          <span className="terminal-title-text">Unknown provider: {chatProvider}</span>
        </div>
      </div>
    )
  }

  const ChatComponent = provider.component

  return (
    <div className="panel-content terminal-panel-content">
      <ChatComponent
        onToggleCollapse={onToggleCollapse}
        approvals={approvals}
        onFocusReview={onFocusReview}
        onDecision={onDecision}
        normalizeApprovalPath={normalizeApprovalPath}
      />
    </div>
  )
}
