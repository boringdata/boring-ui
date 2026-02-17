export const routes = {
  approval: {
    pending: () => ({ path: '/api/approval/pending', query: undefined }),
    decision: () => ({ path: '/api/approval/decision', query: undefined }),
  },
  project: {
    root: () => ({ path: '/api/project', query: undefined }),
  },
  capabilities: {
    get: () => ({ path: '/api/capabilities', query: undefined }),
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
    rename: () => ({ path: '/api/v1/files/rename', query: undefined }),
    move: () => ({ path: '/api/v1/files/move', query: undefined }),
    search: (queryText) => ({ path: '/api/v1/files/search', query: { q: queryText } }),
  },
  git: {
    status: () => ({ path: '/api/v1/git/status', query: undefined }),
    diff: (targetPath) => ({ path: '/api/v1/git/diff', query: { path: targetPath } }),
    show: (targetPath) => ({ path: '/api/v1/git/show', query: { path: targetPath } }),
  },
  sessions: {
    list: () => ({ path: '/api/sessions', query: undefined }),
    create: () => ({ path: '/api/sessions', query: undefined }),
  },
  attachments: {
    upload: () => ({ path: '/api/attachments', query: undefined }),
  },
  ws: {
    plugins: () => ({ path: '/ws/plugins', query: undefined }),
    pty: (query) => ({ path: '/ws/pty', query: query || undefined }),
    claudeStream: (query) => ({ path: '/ws/claude-stream', query: query || undefined }),
  },
}
