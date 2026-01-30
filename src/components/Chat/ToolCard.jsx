import React, { useState, useMemo, useEffect } from 'react'
import { ChevronDown, CheckCircle, AlertCircle, Loader, Clock, Copy, ChevronRight } from 'lucide-react'
import '../../../styles/tool-cards.css'

/**
 * ToolCard Component - Displays tool invocation with parameters and results
 *
 * Renders a beautiful card showing:
 * - Tool name and icon
 * - Execution status (loading, success, error)
 * - Input parameters in a collapsible section
 * - Output/results in a collapsible section
 * - Execution duration
 * - Error messages with actionable feedback
 * - Copy functionality for results
 *
 * @param {Object} props
 * @param {string} props.id - Unique tool invocation ID
 * @param {string} props.toolName - Name of the tool invoked
 * @param {string} props.status - Execution status ('loading', 'success', 'error')
 * @param {Object} props.input - Input parameters passed to tool
 * @param {any} props.output - Output/result from tool execution
 * @param {string} props.error - Error message if status is 'error'
 * @param {number} props.duration - Execution duration in milliseconds
 * @param {string} props.icon - Icon name for the tool
 * @param {Array} props.dependencies - Array of tool IDs this tool depends on
 * @param {boolean} props.expanded - Whether results section is expanded (default: false)
 * @param {Function} props.onExpand - Callback when expand state changes
 * @param {Function} props.onCopy - Callback when copy is clicked
 * @returns {React.ReactElement}
 */
const ToolCard = React.forwardRef(
  (
    {
      id = '',
      toolName = 'Tool',
      status = 'loading',
      input = {},
      output = null,
      error = null,
      duration = null,
      icon = 'Wrench',
      dependencies = [],
      expanded = false,
      onExpand,
      onCopy,
      className = '',
    },
    ref,
  ) => {
    const [isExpanded, setIsExpanded] = useState(expanded)
    const [copied, setCopied] = useState(false)

    // Track render performance
    useEffect(() => {
      const startTime = performance.now()
      return () => {
        const renderTime = performance.now() - startTime
        if (renderTime > 100) {
          console.warn(`ToolCard render took ${renderTime.toFixed(2)}ms`)
        }
      }
    }, [])

    // Toggle expansion and notify parent
    const handleToggleExpand = () => {
      const newState = !isExpanded
      setIsExpanded(newState)
      onExpand?.(id, newState)
    }

    // Handle copy to clipboard
    const handleCopy = async () => {
      try {
        const textToCopy = typeof output === 'string' ? output : JSON.stringify(output, null, 2)
        await navigator.clipboard.writeText(textToCopy)
        setCopied(true)
        onCopy?.(id)
        setTimeout(() => setCopied(false), 2000)
      } catch (err) {
        console.error('Failed to copy:', err)
      }
    }

    // Format duration display
    const durationDisplay = useMemo(() => {
      if (!duration) return null
      if (duration < 1000) return `${duration.toFixed(0)}ms`
      return `${(duration / 1000).toFixed(2)}s`
    }, [duration])

    // Determine status icon and color
    const getStatusIcon = () => {
      switch (status) {
        case 'loading':
          return <Loader className="tool-status-icon-loading" />
        case 'success':
          return <CheckCircle className="tool-status-icon-success" />
        case 'error':
          return <AlertCircle className="tool-status-icon-error" />
        default:
          return null
      }
    }

    // Format JSON-like output for display
    const formatOutput = (data) => {
      if (typeof data === 'string') return data
      if (typeof data === 'object') {
        return JSON.stringify(data, null, 2)
      }
      return String(data)
    }

    return (
      <div
        ref={ref}
        data-tool-id={id}
        className={`tool-card tool-card-${status} ${className}`.trim()}
      >
        {/* Tool Header */}
        <div className="tool-card-header">
          {/* Icon and Name */}
          <div className="tool-card-title-section">
            <div className="tool-card-icon">{getStatusIcon()}</div>
            <div className="tool-card-info">
              <h3 className="tool-card-name">{toolName}</h3>
              {dependencies && dependencies.length > 0 && (
                <p className="tool-card-dependencies">
                  Depends on {dependencies.length} tool{dependencies.length !== 1 ? 's' : ''}
                </p>
              )}
            </div>
          </div>

          {/* Duration and Actions */}
          <div className="tool-card-meta">
            {durationDisplay && (
              <div className="tool-card-duration">
                <Clock size={14} />
                <span>{durationDisplay}</span>
              </div>
            )}

            {output !== null && status === 'success' && (
              <button
                className={`tool-card-copy-button ${copied ? 'tool-card-copy-success' : ''}`}
                onClick={handleCopy}
                title={copied ? 'Copied!' : 'Copy output'}
                aria-label="Copy tool output"
              >
                <Copy size={14} />
              </button>
            )}

            {(output !== null || error) && (
              <button
                className="tool-card-expand-button"
                onClick={handleToggleExpand}
                title={isExpanded ? 'Collapse' : 'Expand'}
                aria-label={isExpanded ? 'Collapse tool details' : 'Expand tool details'}
              >
                <ChevronDown
                  size={16}
                  className={isExpanded ? 'tool-card-expand-open' : ''}
                />
              </button>
            )}
          </div>
        </div>

        {/* Input Parameters Section */}
        {Object.keys(input).length > 0 && (
          <div className="tool-card-inputs">
            <div className="tool-card-section-title">Input Parameters</div>
            <div className="tool-card-params">
              {Object.entries(input).map(([key, value]) => (
                <div key={`input-${key}`} className="tool-card-param">
                  <span className="tool-card-param-name">{key}:</span>
                  <span className="tool-card-param-value">
                    {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Expandable Results Section */}
        {(output !== null || error) && (
          <div className={`tool-card-results ${isExpanded ? 'tool-card-results-expanded' : ''}`}>
            <div className="tool-card-results-content">
              {error ? (
                <div className="tool-card-error-message">
                  <AlertCircle size={16} />
                  <div className="tool-card-error-text">
                    <p className="tool-card-error-title">Error</p>
                    <p className="tool-card-error-body">{error}</p>
                  </div>
                </div>
              ) : (
                <div className="tool-card-output">
                  <div className="tool-card-section-title">Output</div>
                  <pre className="tool-card-output-content">
                    <code>{formatOutput(output)}</code>
                  </pre>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Status Loading Indicator */}
        {status === 'loading' && (
          <div className="tool-card-loading-bar">
            <div className="tool-card-loading-progress" />
          </div>
        )}
      </div>
    )
  },
)

ToolCard.displayName = 'ToolCard'

export default ToolCard
