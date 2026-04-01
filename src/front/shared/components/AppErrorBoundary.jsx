import { Component } from 'react'
import { AlertCircle, RotateCcw } from 'lucide-react'

/**
 * Global error boundary — catches unhandled render errors at the app root.
 * Prevents the white-screen-of-death by showing a branded recovery page.
 */
export default class AppErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('[AppErrorBoundary] Application crashed:', error, errorInfo)
  }

  handleReload = () => {
    window.location.reload()
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="app-error-boundary">
          <div className="app-error-boundary-content">
            <AlertCircle size={48} className="app-error-boundary-icon" />
            <h1 className="app-error-boundary-title">Something went wrong</h1>
            <p className="app-error-boundary-message">
              {this.state.error?.message || 'An unexpected error occurred.'}
            </p>
            <button
              type="button"
              onClick={this.handleReload}
              className="app-error-boundary-reload"
            >
              <RotateCcw size={16} />
              Reload Application
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
