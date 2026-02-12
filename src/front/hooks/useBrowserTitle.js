/**
 * Hook to manage browser document title based on config and project root.
 *
 * Priority:
 * 1. config.branding.titleFormat (function) with folder/workspace context
 * 2. "{folderName} - {brandingName}" pattern
 * 3. config.branding.name or 'Boring UI' as fallback
 */

import { useEffect } from 'react'

/**
 * Set the browser document.title reactively.
 *
 * @param {string|null} projectRoot - Project root path (null = not loaded)
 * @param {Object} [branding] - config.branding object
 */
export function useBrowserTitle(projectRoot, branding) {
  useEffect(() => {
    const folderName = projectRoot
      ? projectRoot.split('/').filter(Boolean).pop()
      : null

    const titleFormat = branding?.titleFormat
    if (typeof titleFormat === 'function') {
      document.title = titleFormat({ folder: folderName, workspace: folderName })
    } else {
      document.title = folderName
        ? `${folderName} - ${branding?.name || 'Boring UI'}`
        : branding?.name || 'Boring UI'
    }
  }, [projectRoot, branding])
}
