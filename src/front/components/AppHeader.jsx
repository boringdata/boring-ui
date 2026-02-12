/**
 * Application header with branding and controls.
 *
 * Extracted from App.jsx lines 1546-1558. Renders the logo/brand
 * area and header controls (theme toggle).
 */

import React from 'react'
import ThemeToggle from './ThemeToggle'

/**
 * @param {Object} props
 * @param {Object} props.config - App config with branding
 * @param {string|null} props.projectRoot - Project root path
 */
export function AppHeader({ config, projectRoot }) {
  return (
    <header className="app-header">
      <div className="app-header-brand">
        <div className="app-header-logo" aria-hidden="true">
          {config.branding?.logo || 'B'}
        </div>
        <div className="app-header-title">
          {projectRoot?.split('/').pop() || config.branding?.name || 'Workspace'}
        </div>
      </div>
      <div className="app-header-controls">
        <ThemeToggle />
      </div>
    </header>
  )
}

export default AppHeader
