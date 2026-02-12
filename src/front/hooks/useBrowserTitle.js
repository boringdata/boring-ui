/**
 * Browser document title management based on config and project root.
 *
 * Extracted from App.jsx lines 1097-1109. Sets document.title using
 * config.branding.titleFormat (function) or a fallback pattern.
 */

import { useEffect } from 'react'

const DEFAULT_APP_NAME = 'Boring UI'

/**
 * Extracts the folder name from a project root path.
 *
 * @param {string|null} projectRoot - Absolute project root path
 * @returns {string|null} Last path segment, or null
 */
export function getFolderName(projectRoot) {
  if (!projectRoot) return null
  return projectRoot.split('/').filter(Boolean).pop() || null
}

/**
 * Computes the browser title from config and project root.
 *
 * Priority:
 * 1. config.branding.titleFormat({ folder, workspace }) if it's a function
 * 2. "{folderName} - {appName}" if projectRoot is available
 * 3. appName (config.branding.name or 'Boring UI')
 *
 * @param {Object} config - Application config
 * @param {string|null} projectRoot - Project root path
 * @returns {string} Computed title
 */
export function computeTitle(config, projectRoot) {
  const folderName = getFolderName(projectRoot)
  const titleFormat = config?.branding?.titleFormat
  const appName = config?.branding?.name || DEFAULT_APP_NAME

  if (typeof titleFormat === 'function') {
    return titleFormat({ folder: folderName, workspace: folderName })
  }

  return folderName ? `${folderName} - ${appName}` : appName
}

/**
 * Sets document.title based on config branding and project root.
 *
 * @param {Object} config - Application config with optional branding
 * @param {string|null} projectRoot - Project root path
 */
export function useBrowserTitle(config, projectRoot) {
  useEffect(() => {
    document.title = computeTitle(config, projectRoot)
  }, [projectRoot, config?.branding])
}
