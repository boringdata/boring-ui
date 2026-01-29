/**
 * Example configuration for boring-ui
 * Copy this file to app.config.js and customize for your app
 */

export default {
  // App branding
  branding: {
    name: 'My App',           // Displayed in header
    logo: 'M',                // Single character or React component
    // Format for document.title - receives { folder, workspace } context
    titleFormat: (ctx) => ctx.workspace ? `${ctx.workspace} - My App` : 'My App',
  },

  // FileTree configuration
  fileTree: {
    // Sections to show (in order) - keys should match paths from /api/config
    sections: [
      { key: 'documents', label: 'Documents', icon: 'FileText' },
      { key: 'queries', label: 'Queries', icon: 'Search' },
      { key: 'config', label: 'Configuration', icon: 'Settings' },
    ],
    // Files to show at top of tree with config icon
    configFiles: ['config.yaml', 'pyproject.toml'],
    // Polling intervals (ms)
    gitPollInterval: 5000,
    treePollInterval: 3000,
  },

  // LocalStorage key configuration
  storage: {
    prefix: 'myapp',          // Keys will be: myapp-layout, myapp-tabs, etc.
    layoutVersion: 1,         // Increment to force layout reset for all users
    // Optional: migrate old localStorage keys to new ones
    // migrateLegacyKeys: { 'old-key': 'new-key' },
  },

  // Panel configuration
  panels: {
    // Panels that must always exist
    essential: ['filetree', 'terminal'],
    // Default panel sizes (px)
    defaults: {
      filetree: 280,
      terminal: 400,
    },
    // Minimum sizes
    min: {
      filetree: 180,
      terminal: 250,
    },
    // Collapsed sizes
    collapsed: {
      filetree: 48,
      terminal: 48,
    },
  },

  // API configuration
  api: {
    // Base URL (defaults to '' for same-origin)
    baseUrl: import.meta.env.VITE_API_URL || '',
  },

  // Feature flags
  features: {
    gitStatus: true,          // Show git status badges
    search: true,             // Enable file search
    cloudMode: true,          // Enable cloud mode features (user menu, etc.)
    workflows: false,         // Enable workflow panels (kurt-core specific)
  },
}
