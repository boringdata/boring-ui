import { Loader2 } from 'lucide-react'

/**
 * Full-screen loading state shown during app boot.
 * This is the first thing users see — should feel polished and branded.
 */
export default function WorkspaceLoading({
  title = 'Opening workspace',
  message = 'Connecting to backend services...',
  logo = 'B',
}) {
  return (
    <div className="workspace-loading" role="status" aria-live="polite">
      <div className="workspace-loading-brand">{logo}</div>
      <Loader2 className="workspace-loading-icon" size={32} />
      <p className="workspace-loading-title">{title}</p>
      <p className="workspace-loading-message">{message}</p>
    </div>
  )
}
