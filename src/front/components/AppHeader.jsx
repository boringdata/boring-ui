/**
 * Application header with branding and controls.
 *
 * @param {Object} props
 * @param {Object} props.config - App configuration
 * @param {string|null} props.projectRoot - Current project root path
 * @param {React.ReactNode} [props.children] - Header control elements (e.g. ThemeToggle)
 */
export default function AppHeader({ config, projectRoot, children }) {
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
        {children}
      </div>
    </header>
  )
}
