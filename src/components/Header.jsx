import { useEffect } from 'react';
import { useConfig } from '../config';
import ThemeToggle from './ThemeToggle';
import UserMenu from './UserMenu';

/**
 * Application header component with configurable branding
 *
 * Uses the config context to display:
 * - Logo from config.branding.logo (string character or React component)
 * - App name from config.branding.name
 * - Document title via config.branding.titleFormat
 *
 * @param {object} props
 * @param {object} [props.userContext] - User context with is_cloud_mode, user, workspace
 * @param {string} [props.projectRoot] - Project root path for title formatting
 * @returns {React.ReactElement}
 *
 * @example
 * ```jsx
 * import { Header } from './components'
 *
 * <Header
 *   userContext={{ is_cloud_mode: true, user: { email: 'user@example.com' }, workspace: { name: 'My Workspace' } }}
 *   projectRoot="/path/to/project"
 * />
 * ```
 */
export default function Header({ userContext, projectRoot }) {
  const { branding } = useConfig();

  // Set document title based on branding.titleFormat
  useEffect(() => {
    const workspaceName = userContext?.workspace?.name;
    // Extract folder name from projectRoot
    const folderName = projectRoot ? projectRoot.split('/').filter(Boolean).pop() : undefined;

    // Determine workspace name for title (skip if it looks like a UUID)
    const workspace = workspaceName && !workspaceName.includes('-') ? workspaceName : undefined;

    // Call titleFormat function with context
    if (typeof branding.titleFormat === 'function') {
      document.title = branding.titleFormat({ folder: folderName, workspace });
    } else {
      // Fallback if titleFormat is not a function
      document.title = workspace ? `${workspace} - ${branding.name}` : branding.name;
    }
  }, [branding, userContext?.workspace?.name, projectRoot]);

  // Render logo - can be a string (char) or React component
  const renderLogo = () => {
    if (typeof branding.logo === 'string') {
      return branding.logo;
    }
    // If it's a React component, render it
    if (typeof branding.logo === 'function') {
      const LogoComponent = branding.logo;
      return <LogoComponent />;
    }
    // If it's a React element, return it directly
    if (branding.logo && typeof branding.logo === 'object') {
      return branding.logo;
    }
    // Fallback to first character of name
    return branding.name.charAt(0).toUpperCase();
  };

  return (
    <header className="app-header">
      <div className="app-header-brand">
        <div className="app-header-logo">{renderLogo()}</div>
        <span className="app-header-title">{branding.name}</span>
      </div>
      <div className="app-header-controls">
        <ThemeToggle />
        {userContext?.is_cloud_mode && userContext?.user && (
          <UserMenu
            email={userContext.user.email}
            workspaceName={userContext.workspace?.name || 'Workspace'}
            workspaceId={userContext.workspace?.id || ''}
          />
        )}
      </div>
    </header>
  );
}
