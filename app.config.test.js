/**
 * Test Configuration for boring-ui
 * Used for testing the application with default settings
 */

export default {
  branding: {
    name: 'boring-ui Test',
    logo: 'T',
    titleFormat: (ctx) => ctx.workspace ? `${ctx.workspace} - Test UI` : 'Test UI',
  },

  fileTree: {
    sections: [
      { key: 'documents', label: 'Documents', icon: 'FileText' },
      { key: 'queries', label: 'Queries', icon: 'Search' },
    ],
    configFiles: ['*.config.js', 'app.toml', 'README.md'],
    gitPollInterval: 5000,
    treePollInterval: 3000,
  },

  storage: {
    prefix: 'boring-ui-test',
    layoutVersion: 1,
  },

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

  api: {
    baseURL: process.env.VITE_API_URL || 'http://localhost:8000',
  },

  features: {
    gitStatus: true,
    search: true,
    cloudMode: false,
    workflows: false,
  },

  styles: {
    light: {
      accent: '#3b82f6',
      accentHover: '#2563eb',
      accentLight: '#dbeafe',
    },
    dark: {
      accent: '#60a5fa',
      accentHover: '#93c5fd',
      accentLight: '#1e3a8a',
    },
  },
}
