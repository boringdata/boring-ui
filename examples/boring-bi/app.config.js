/**
 * Boring BI configuration for boring-ui
 * A business intelligence dashboard viewer application
 */

export default {
  // App branding
  branding: {
    name: 'Boring BI',
    logo: 'B',
    titleFormat: (ctx) => ctx.workspace ? `${ctx.workspace} - Boring BI` : 'Boring BI',
  },

  // FileTree configuration
  fileTree: {
    // Sections to show (in order) - keys should match paths from /api/config
    sections: [
      { key: 'dashboards', label: 'Dashboards', icon: 'LayoutDashboard' },
      { key: 'models', label: 'Models', icon: 'Database' },
      { key: 'profiles', label: 'Profiles', icon: 'Users' },
    ],
    // Files to show at top of tree with config icon
    // Supports exact matches and glob patterns (e.g., '*.config', '*.toml')
    configFiles: ['pyproject.toml', 'bbi.config', '*.config'],
    // Polling intervals (ms)
    gitPollInterval: 5000,
    treePollInterval: 3000,
  },

  // LocalStorage key configuration
  storage: {
    prefix: 'bbi',
    layoutVersion: 1,
  },

  // Panel configuration
  panels: {
    essential: ['filetree', 'terminal'],
    defaults: {
      filetree: 280,
      terminal: 400,
    },
    min: {
      filetree: 180,
      terminal: 250,
    },
    collapsed: {
      filetree: 48,
      terminal: 48,
    },
  },

  // API configuration
  api: {
    baseUrl: import.meta.env.VITE_API_URL || '',
  },

  // Feature flags
  features: {
    gitStatus: true,
    search: true,
    cloudMode: true,
    workflows: false,
  },
}
