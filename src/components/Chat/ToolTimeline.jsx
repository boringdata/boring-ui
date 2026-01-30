import React, { useMemo } from 'react'
import ToolCard from './ToolCard'
import '../../../styles/tool-cards.css'

/**
 * ToolTimeline Component - Shows history of tool invocations in sequence
 *
 * Renders:
 * - Vertical timeline of tool executions
 * - Timeline connectors between related tools
 * - Tool dependency relationships
 * - Search/filter functionality for finding specific tools
 * - Execution order and timing
 * - Collapsible cards for each tool invocation
 *
 * @param {Object} props
 * @param {Array} props.tools - Array of tool invocation objects
 *   Each tool object should have: id, toolName, status, input, output, error, duration, dependencies
 * @param {Function} props.onToolExpand - Callback when tool card expand state changes
 * @param {Function} props.onToolCopy - Callback when tool output is copied
 * @param {string} props.searchQuery - Filter tools by name/description
 * @param {boolean} props.showAll - Whether to show all tools or only successful ones (default: true)
 * @param {string} props.className - Additional CSS classes
 * @returns {React.ReactElement}
 */
const ToolTimeline = React.forwardRef(
  (
    {
      tools = [],
      onToolExpand,
      onToolCopy,
      searchQuery = '',
      showAll = true,
      className = '',
    },
    ref,
  ) => {
    // Filter tools based on search query and showAll flag
    const filteredTools = useMemo(() => {
      return tools.filter((tool) => {
        // Filter by status if not showing all
        if (!showAll && tool.status !== 'success') {
          return false
        }

        // Filter by search query
        if (searchQuery.trim()) {
          const query = searchQuery.toLowerCase()
          return (
            tool.toolName.toLowerCase().includes(query) ||
            (tool.id && tool.id.toLowerCase().includes(query))
          )
        }

        return true
      })
    }, [tools, searchQuery, showAll])

    // Build tool dependency map for visualization
    const toolDependencyMap = useMemo(() => {
      const map = new Map()
      tools.forEach((tool) => {
        map.set(tool.id, tool.dependencies || [])
      })
      return map
    }, [tools])

    // Find tools that depend on a given tool
    const getToolsDependingOn = (toolId) => {
      return tools.filter(
        (tool) => tool.dependencies && tool.dependencies.includes(toolId),
      )
    }

    // Track expand states
    const [expandedTools, setExpandedTools] = React.useState({})

    const handleToolExpand = (toolId, isExpanded) => {
      setExpandedTools((prev) => ({
        ...prev,
        [toolId]: isExpanded,
      }))
      onToolExpand?.(toolId, isExpanded)
    }

    // Calculate tool chain depth for visualization
    const getToolDepth = (toolId, visited = new Set()) => {
      if (visited.has(toolId)) return 0
      visited.add(toolId)

      const dependencies = toolDependencyMap.get(toolId) || []
      if (dependencies.length === 0) return 0

      return 1 + Math.max(...dependencies.map((depId) => getToolDepth(depId, visited)))
    }

    if (tools.length === 0) {
      return (
        <div className={`tool-timeline ${className}`.trim()}>
          <div className="tool-timeline-empty">
            <p>No tools have been invoked yet.</p>
          </div>
        </div>
      )
    }

    if (filteredTools.length === 0) {
      return (
        <div className={`tool-timeline ${className}`.trim()}>
          <div className="tool-timeline-empty">
            <p>No tools match your search: "{searchQuery}"</p>
          </div>
        </div>
      )
    }

    return (
      <div
        ref={ref}
        className={`tool-timeline ${className}`.trim()}
      >
        {/* Timeline header */}
        <div className="tool-timeline-header">
          <h2 className="tool-timeline-title">
            Tool Execution Timeline
            {filteredTools.length < tools.length && (
              <span className="tool-timeline-count">
                {filteredTools.length} of {tools.length}
              </span>
            )}
          </h2>
        </div>

        {/* Tool cards in timeline */}
        <div className="tool-timeline-list">
          {filteredTools.map((tool, index) => {
            const isLast = index === filteredTools.length - 1
            const nextTool = !isLast ? filteredTools[index + 1] : null

            // Check if next tool depends on current tool
            const hasConnection =
              nextTool &&
              nextTool.dependencies &&
              nextTool.dependencies.includes(tool.id)

            return (
              <div key={tool.id} className="tool-timeline-item">
                {/* Timeline connector (vertical line) */}
                {!isLast && (
                  <div
                    className={`tool-timeline-connector ${
                      hasConnection ? 'tool-timeline-connector-dependent' : ''
                    }`}
                  />
                )}

                {/* Tool card */}
                <ToolCard
                  id={tool.id}
                  toolName={tool.toolName}
                  status={tool.status}
                  input={tool.input}
                  output={tool.output}
                  error={tool.error}
                  duration={tool.duration}
                  icon={tool.icon}
                  dependencies={tool.dependencies}
                  expanded={expandedTools[tool.id] || false}
                  onExpand={handleToolExpand}
                  onCopy={onToolCopy}
                  className="tool-timeline-card"
                />

                {/* Dependency indicators */}
                {tool.dependencies && tool.dependencies.length > 0 && (
                  <div className="tool-timeline-dependencies">
                    <div className="tool-timeline-dependency-label">
                      Depends on:
                    </div>
                    <div className="tool-timeline-dependency-list">
                      {tool.dependencies.map((depId) => {
                        const depTool = tools.find((t) => t.id === depId)
                        return (
                          <div key={depId} className="tool-timeline-dependency-item">
                            <span className="tool-timeline-dependency-name">
                              {depTool?.toolName || depId}
                            </span>
                            <span className={`tool-timeline-dependency-status tool-timeline-dependency-status-${depTool?.status}`}>
                              {depTool?.status === 'success' ? '✓' : '○'}
                            </span>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}

                {/* Tools depending on this one */}
                {getToolsDependingOn(tool.id).length > 0 && (
                  <div className="tool-timeline-dependents">
                    <div className="tool-timeline-dependent-label">
                      Used by:
                    </div>
                    <div className="tool-timeline-dependent-list">
                      {getToolsDependingOn(tool.id).map((depTool) => (
                        <div key={depTool.id} className="tool-timeline-dependent-item">
                          <span className="tool-timeline-dependent-name">
                            {depTool.toolName}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Timeline summary stats */}
        {tools.length > 0 && (
          <div className="tool-timeline-stats">
            <div className="tool-timeline-stat">
              <span className="tool-timeline-stat-label">Total Tools:</span>
              <span className="tool-timeline-stat-value">{tools.length}</span>
            </div>
            <div className="tool-timeline-stat">
              <span className="tool-timeline-stat-label">Successful:</span>
              <span className="tool-timeline-stat-value tool-timeline-stat-success">
                {tools.filter((t) => t.status === 'success').length}
              </span>
            </div>
            <div className="tool-timeline-stat">
              <span className="tool-timeline-stat-label">Failed:</span>
              <span className="tool-timeline-stat-value tool-timeline-stat-error">
                {tools.filter((t) => t.status === 'error').length}
              </span>
            </div>
            {tools.some((t) => t.duration) && (
              <div className="tool-timeline-stat">
                <span className="tool-timeline-stat-label">Total Time:</span>
                <span className="tool-timeline-stat-value">
                  {(
                    tools.reduce((sum, t) => sum + (t.duration || 0), 0) / 1000
                  ).toFixed(2)}
                  s
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    )
  },
)

ToolTimeline.displayName = 'ToolTimeline'

export default ToolTimeline
