import { FileSearch } from 'lucide-react'
import { getConfig } from '../config'

export default function EmptyPanel() {
  const config = getConfig()
  const message = config?.branding?.emptyPanelMessage || 'Open a file from the left pane to start'
  return (
    <div className="panel-content empty-panel">
      <div className="empty-panel-content">
        <FileSearch className="empty-panel-icon" size={20} aria-hidden="true" />
        <p className="empty-panel-message">{message}</p>
        <p className="empty-panel-hint">Press Ctrl+P to quickly find a file.</p>
      </div>
    </div>
  )
}
