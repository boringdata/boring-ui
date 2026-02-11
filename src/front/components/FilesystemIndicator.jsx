/**
 * Filesystem Source Indicator
 *
 * Shows where the file tree files are coming from:
 * - Local: Shows the workspace path
 * - Sandbox: Shows the sandbox URL
 * - Sprites: Shows Sprites.dev info
 */

import { useEffect, useState } from 'react'
import { Server, HardDrive, Cloud, AlertCircle } from 'lucide-react'
import './filesystem-indicator.css'

export default function FilesystemIndicator() {
  const [source, setSource] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const getFilesystemSource = async () => {
      try {
        // Fetch backend capabilities to see workspace configuration
        const response = await fetch('/api/capabilities')
        const data = await response.json()

        // For now, show the filesystem indicator based on environment hints
        // In the future, we could query an endpoint that returns the actual workspace path
        const workspacePath = process.env.VITE_WORKSPACE_PATH || '/home/ubuntu/projects/boring-ui'

        // Detect filesystem source from path or env var
        const fsSource = process.env.VITE_FILESYSTEM_SOURCE || 'local'

        if (fsSource === 'sprites' || workspacePath.includes('sprites')) {
          // Files are on Sprites.dev
          setSource({
            type: 'sprites',
            label: 'Sprites.dev',
            icon: 'cloud',
            details: workspacePath,
            color: 'var(--color-sprites)',
          })
        } else if (fsSource === 'sandbox' || workspacePath.includes('sandbox')) {
          // Files are in sandbox workspace
          setSource({
            type: 'sandbox',
            label: 'Sandbox Filesystem',
            icon: 'server',
            details: workspacePath,
            color: 'var(--color-sandbox)',
          })
        } else {
          // Local filesystem
          setSource({
            type: 'local',
            label: 'Local Filesystem',
            icon: 'harddrive',
            details: workspacePath,
            color: 'var(--color-local)',
          })
        }
      } catch (error) {
        console.error('Failed to determine filesystem source:', error)
        setSource({
          type: 'unknown',
          label: 'Filesystem',
          icon: 'alert',
          details: 'Unable to determine source',
          color: 'var(--color-error)',
        })
      } finally {
        setLoading(false)
      }
    }

    getFilesystemSource()
  }, [])

  if (loading) {
    return (
      <div className="filesystem-indicator loading">
        <div className="indicator-spinner"></div>
      </div>
    )
  }

  if (!source) {
    return null
  }

  const getIcon = () => {
    switch (source.icon) {
      case 'cloud':
        return <Cloud size={14} />
      case 'server':
        return <Server size={14} />
      case 'harddrive':
        return <HardDrive size={14} />
      case 'alert':
        return <AlertCircle size={14} />
      default:
        return <HardDrive size={14} />
    }
  }

  return (
    <div className="filesystem-indicator" data-source={source.type}>
      <div className="indicator-icon" style={{ color: source.color }}>
        {getIcon()}
      </div>
      <div className="indicator-content">
        <div className="indicator-label">{source.label}</div>
        <div className="indicator-details">
          {source.url ? (
            <a href={source.url} target="_blank" rel="noopener noreferrer" className="indicator-url">
              {source.url}
            </a>
          ) : (
            <code className="indicator-path">{source.details}</code>
          )}
        </div>
      </div>
      <div className="indicator-badge" title={`Source: ${source.type}`}>
        {source.type.toUpperCase().substring(0, 3)}
      </div>
    </div>
  )
}
