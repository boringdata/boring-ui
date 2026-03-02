import { Loader2 } from 'lucide-react'

export default function PaneLoadingState({ paneId, paneTitle }) {
  return (
    <div className="pane-loading-state" role="status" aria-live="polite">
      <Loader2 className="pane-loading-icon" size={36} />
      <h3 className="pane-loading-title">{paneTitle || paneId} Loading</h3>
      <p className="pane-loading-message">
        Waiting for backend capabilities. This should resolve automatically.
      </p>
    </div>
  )
}
