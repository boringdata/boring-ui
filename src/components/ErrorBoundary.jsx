import React, { Component } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { clsx } from 'clsx';
import { logError } from '../utils/errorHandling';
import Button from './primitives/Button';

/**
 * Error Boundary Component
 * Catches React rendering errors and displays a fallback UI with recovery options
 *
 * @component
 * @example
 * ```jsx
 * <ErrorBoundary onError={(error, errorInfo) => console.log(error)}>
 *   <YourComponent />
 * </ErrorBoundary>
 * ```
 */
class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      isCollapsed: false,
    };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    // Update state
    this.setState({
      error,
      errorInfo,
    });

    // Log error for debugging
    logError(error, {
      type: 'React Error Boundary',
      componentStack: errorInfo.componentStack,
    });

    // Call onError callback if provided
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      isCollapsed: true,
    });

    // Call onReset callback if provided
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  toggleDetails = () => {
    this.setState(prev => ({ isCollapsed: !prev.isCollapsed }));
  };

  render() {
    if (this.state.hasError) {
      const { error, errorInfo, isCollapsed } = this.state;
      const isDevelopment = process.env.NODE_ENV === 'development';

      return (
        <div
          role="alert"
          className={clsx(
            'relative border rounded-lg p-6 flex gap-4',
            'bg-error-bg border-error/30',
            this.props.className
          )}
        >
          {/* Icon */}
          <AlertTriangle
            size={24}
            className="flex-shrink-0 text-error mt-1"
            aria-hidden="true"
          />

          {/* Content */}
          <div className="flex-1 min-w-0">
            {/* Title */}
            <h2 className="text-lg font-semibold text-error mb-2">
              {this.props.title || 'Something went wrong'}
            </h2>

            {/* Message */}
            <p className="text-sm text-foreground/70 mb-4">
              {this.props.message ||
                'An unexpected error occurred. Please try refreshing the page or contact support if the problem persists.'}
            </p>

            {/* Error Details (Development Only) */}
            {isDevelopment && error && (
              <div className="mt-4 space-y-3">
                <div>
                  <button
                    onClick={this.toggleDetails}
                    className="text-sm font-medium text-info hover:underline flex items-center gap-2"
                  >
                    {isCollapsed ? '▶' : '▼'} {isCollapsed ? 'Show' : 'Hide'} Details
                  </button>
                </div>

                {!isCollapsed && (
                  <div className="bg-black/10 dark:bg-white/10 rounded p-3 space-y-2">
                    <div>
                      <p className="text-xs font-mono text-foreground/60">Error Message:</p>
                      <p className="text-xs font-mono text-error break-all">
                        {error.toString()}
                      </p>
                    </div>

                    {errorInfo?.componentStack && (
                      <div>
                        <p className="text-xs font-mono text-foreground/60">Component Stack:</p>
                        <pre className="text-xs font-mono text-foreground/60 overflow-auto max-h-40 whitespace-pre-wrap break-words">
                          {errorInfo.componentStack}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-3 mt-6 flex-wrap">
              <Button
                onClick={this.handleReset}
                variant="primary"
                size="sm"
                className="flex items-center gap-2"
              >
                <RefreshCw size={16} />
                Try Again
              </Button>

              {this.props.onContactSupport && (
                <Button
                  onClick={this.props.onContactSupport}
                  variant="secondary"
                  size="sm"
                >
                  Contact Support
                </Button>
              )}
            </div>
          </div>

          {/* Close button (if dismissible) */}
          {this.props.dismissible && (
            <button
              onClick={() => this.setState({ hasError: false })}
              className="flex-shrink-0 rounded hover:bg-black/10 dark:hover:bg-white/10 p-2 transition-colors"
              aria-label="Dismiss error"
            >
              <span className="text-foreground/60">×</span>
            </button>
          )}
        </div>
      );
    }

    return this.props.children;
  }
}

ErrorBoundary.defaultProps = {
  dismissible: false,
  onError: null,
  onReset: null,
  onContactSupport: null,
  title: null,
  message: null,
  className: null,
};

export default ErrorBoundary;
