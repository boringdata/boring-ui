import { Component } from 'react'
import { AlertCircle, RotateCcw } from 'lucide-react'

/**
 * Error boundary for DockView panels.
 *
 * Catches render errors in individual panels so a crash in one panel
 * (e.g., Editor, Terminal, Agent) doesn't take down the entire app.
 * Shows a recovery UI with a retry button.
 */
export default class PanelErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error(
      `[PanelErrorBoundary] ${this.props.panelName || 'Panel'} crashed:`,
      error,
      errorInfo,
    )
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="pane-error-state">
          <AlertCircle className="pane-error-icon" size={48} />
          <h3 className="pane-error-title">
            {this.props.panelName || 'Panel'} Crashed
          </h3>
          <p className="pane-error-message">
            {this.state.error?.message || 'An unexpected error occurred.'}
          </p>
          <button
            type="button"
            onClick={this.handleRetry}
            className="pane-error-retry"
          >
            <RotateCcw size={14} />
            Retry
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
