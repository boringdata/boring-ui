/**
 * Kurt Core configuration for boring-ui
 * A workflow management application with projects and sources
 */

export default {
  // App branding
  branding: {
    name: 'Kurt',
    logo: 'K',
    titleFormat: (ctx) => ctx.workspace ? `${ctx.workspace} - Kurt` : 'Kurt',
  },

  // FileTree configuration
  fileTree: {
    // Sections to show (in order) - keys should match paths from /api/config
    sections: [
      { key: 'projects', label: 'Projects', icon: 'FolderKanban' },
      { key: 'workflows', label: 'Workflows', icon: 'GitBranch' },
      { key: 'sources', label: 'Sources', icon: 'Database' },
    ],
    // Files to show at top of tree with config icon
    // Supports exact matches and glob patterns (e.g., '*.config', '*.toml')
    configFiles: ['kurt.config', '*.config'],
    // Polling intervals (ms)
    gitPollInterval: 5000,
    treePollInterval: 3000,
  },

  // LocalStorage key configuration
  storage: {
    prefix: 'kurt-web',
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
    workflows: true,  // Enable workflow components from examples/kurt/
  },

  // Workflow components reference (from examples/kurt/)
  // These components provide:
  // - WorkflowList: List and filter workflows
  // - WorkflowRow: Individual workflow display with expand/collapse
  // - WorkflowsPanel: Panel container for workflow management
  // - WorkflowTerminalPanel: Terminal panel for workflow output
}
