export const routes = {
  approval: {
    pending: () => ({ path: '/api/approval/pending' }),
    decision: () => ({ path: '/api/approval/decision' }),
  },
  project: {
    root: () => ({ path: '/api/project' }),
  },
  capabilities: {
    get: () => ({ path: '/api/capabilities' }),
  },
  config: {
    get: (configPath) => ({
      path: '/api/config',
      query: configPath ? { config_path: configPath } : undefined,
    }),
  },
  files: {
    list: (targetPath) => ({ path: '/api/v1/files/list', query: { path: targetPath } }),
    read: (targetPath) => ({ path: '/api/v1/files/read', query: { path: targetPath } }),
    write: (targetPath) => ({ path: '/api/v1/files/write', query: { path: targetPath } }),
    delete: (targetPath) => ({ path: '/api/v1/files/delete', query: { path: targetPath } }),
    rename: () => ({ path: '/api/v1/files/rename' }),
    move: () => ({ path: '/api/v1/files/move' }),
    search: (queryText) => ({ path: '/api/v1/files/search', query: { q: queryText } }),
  },
  git: {
    status: () => ({ path: '/api/v1/git/status' }),
    diff: (targetPath) => ({ path: '/api/v1/git/diff', query: { path: targetPath } }),
    show: (targetPath) => ({ path: '/api/v1/git/show', query: { path: targetPath } }),
  },
  sessions: {
    list: () => ({ path: '/api/sessions' }),
    create: () => ({ path: '/api/sessions' }),
  },
  attachments: {
    upload: () => ({ path: '/api/attachments' }),
  },
  ws: {
    plugins: () => ({ path: '/ws/plugins' }),
    pty: (query) => ({ path: '/ws/pty', query }),
    claudeStream: (query) => ({ path: '/ws/claude-stream', query }),
  },
}
