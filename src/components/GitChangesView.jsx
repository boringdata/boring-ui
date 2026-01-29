import React from 'react'
import { Check, FileText } from 'lucide-react'
import { useGitStatus, STATUS_CONFIG } from '../hooks/useGitStatus'

/**
 * GitChangesView - Displays a list of changed files with their git status
 *
 * Uses useGitStatus hook for automatic polling and API integration
 *
 * @param {object} props
 * @param {function} [props.onOpenDiff] - Callback when a file is clicked (path, status)
 * @param {string} [props.activeDiffFile] - Currently active diff file path
 * @param {number} [props.pollInterval] - Custom poll interval (uses config default if not provided)
 */
export default function GitChangesView({ onOpenDiff, activeDiffFile, pollInterval }) {
  const { status, loading, error } = useGitStatus({
    polling: true,
    pollInterval,
  })

  // Extract files from status
  const changes = status?.files || {}

  const handleFileClick = (path, status) => {
    if (onOpenDiff) {
      onOpenDiff(path, status)
    }
  }

  const getFileName = (path) => {
    const parts = path.split('/')
    return parts[parts.length - 1]
  }

  const getDirectory = (path) => {
    const parts = path.split('/')
    if (parts.length <= 1) return ''
    return parts.slice(0, -1).join('/')
  }

  // Group files by status
  const groupedChanges = Object.entries(changes).reduce((acc, [path, status]) => {
    if (!acc[status]) acc[status] = []
    acc[status].push(path)
    return acc
  }, {})

  // Order: Modified, Added, Untracked, Deleted
  const statusOrder = ['M', 'A', 'U', 'D']

  if (loading) {
    return (
      <div className="git-changes-view">
        <div className="git-changes-loading">Loading changes...</div>
      </div>
    )
  }

  // Handle git not available
  if (status && !status.available) {
    return (
      <div className="git-changes-view">
        <div className="git-changes-error">Git not available</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="git-changes-view">
        <div className="git-changes-error">{error.message || 'Failed to fetch git status'}</div>
      </div>
    )
  }

  const totalChanges = Object.keys(changes).length

  if (totalChanges === 0) {
    return (
      <div className="git-changes-view">
        <div className="git-changes-empty">
          <Check className="git-changes-empty-icon" size={24} />
          <span>No changes</span>
        </div>
      </div>
    )
  }

  return (
    <div className="git-changes-view">
      <div className="git-changes-summary">
        {totalChanges} changed file{totalChanges !== 1 ? 's' : ''}
      </div>
      <div className="git-changes-list">
        {statusOrder.map((status) => {
          const files = groupedChanges[status]
          if (!files || files.length === 0) return null
          const config = STATUS_CONFIG[status]

          return (
            <div key={status} className="git-changes-group">
              <div className="git-changes-group-header">
                <span
                  className={`git-status-badge ${config.className}`}
                  style={{ backgroundColor: `${config.color}20`, color: config.color }}
                >
                  {status}
                </span>
                <span className="git-changes-group-label">
                  {config.label} ({files.length})
                </span>
              </div>
              {files.map((path) => {
                const isActive = activeDiffFile === path
                return (
                  <div
                    key={path}
                    className={`git-change-item ${isActive ? 'git-change-item-active' : ''}`}
                    onClick={() => handleFileClick(path, status)}
                  >
                    <span className="git-change-icon"><FileText size={14} /></span>
                    <div className="git-change-info">
                      <span className={`git-change-name file-name-${status.toLowerCase()}`}>
                        {getFileName(path)}
                      </span>
                      {getDirectory(path) && (
                        <span className="git-change-path">{getDirectory(path)}</span>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )
        })}
      </div>
    </div>
  )
}
