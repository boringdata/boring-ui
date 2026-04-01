import { Bot, Code, FileText, GitBranch, Search } from 'lucide-react'
import { getConfig } from '../config'

const CAPABILITIES = [
  { icon: Bot, label: 'Ask the Agent to write, debug, or explain code' },
  { icon: FileText, label: 'Browse and edit files from the sidebar' },
  { icon: Search, label: 'Search across your codebase' },
  { icon: Code, label: 'Run commands in the terminal' },
  { icon: GitBranch, label: 'Review diffs and manage git changes' },
]

const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad|iPod/.test(navigator.platform)

export default function EmptyPanel() {
  const config = getConfig()
  const branding = config?.branding || {}
  const title = branding.emptyPanelTitle || 'Welcome'
  const message = branding.emptyPanelMessage || 'Open a file or start a conversation with the Agent'

  return (
    <div className="panel-content empty-panel">
      <div className="empty-panel-content empty-state">
        <p className="empty-state-title">{title}</p>
        <p className="empty-state-message empty-panel-message">{message}</p>
        <ul className="empty-state-capabilities">
          {CAPABILITIES.map(({ icon: Icon, label }) => (
            <li key={label} className="empty-state-capability">
              <Icon size={15} aria-hidden="true" />
              <span>{label}</span>
            </li>
          ))}
        </ul>
        <p className="empty-state-hint empty-panel-hint">
          {branding.emptyPanelHint || (
            <>
              <kbd>{isMac ? '⌘' : 'Ctrl'}</kbd><kbd>P</kbd>
              <span>to quick-search files</span>
            </>
          )}
        </p>
      </div>
    </div>
  )
}
