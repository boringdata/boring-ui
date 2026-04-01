const encodeSegment = (value) => encodeURIComponent(String(value || '').trim())

const normalizeWorkspaceSubpath = (subpath) =>
  String(subpath || '')
    .replace(/^\/+/, '')
    .trim()

export const routeHref = (route) => {
  const path = String(route?.path || '').trim() || '/'
  const query = route?.query
  if (!query) return path
  const qs = new URLSearchParams()
  Object.entries(query).forEach(([key, value]) => {
    if (value === undefined || value === null) return
    if (Array.isArray(value)) {
      value.forEach((entry) => {
        if (entry !== undefined && entry !== null) qs.append(key, String(entry))
      })
      return
    }
    qs.set(key, String(value))
  })
  const queryString = qs.toString()
  return queryString ? `${path}?${queryString}` : path
}

export const routes = {
  approval: {
    pending: () => ({ path: '/api/approval/pending', query: undefined }),
    decision: () => ({ path: '/api/approval/decision', query: undefined }),
  },
  controlPlane: {
    auth: {
      login: (redirectUri) => ({
        path: '/auth/login',
        query: redirectUri ? { redirect_uri: redirectUri } : undefined,
      }),
      logout: () => ({ path: '/auth/logout', query: undefined }),
      settings: (workspaceId) => ({
        path: '/auth/settings',
        query: workspaceId ? { workspace_id: workspaceId } : undefined,
      }),
    },
    me: {
      get: () => ({ path: '/api/v1/me', query: undefined }),
      settings: {
        get: () => ({ path: '/api/v1/me/settings', query: undefined }),
        update: () => ({ path: '/api/v1/me/settings', query: undefined }),
      },
    },
    workspaces: {
      list: () => ({ path: '/api/v1/workspaces', query: undefined }),
      create: () => ({ path: '/api/v1/workspaces', query: undefined }),
      update: (workspaceId) => ({
        path: `/api/v1/workspaces/${encodeSegment(workspaceId)}`,
        query: undefined,
      }),
      delete: (workspaceId) => ({
        path: `/api/v1/workspaces/${encodeSegment(workspaceId)}`,
        query: undefined,
      }),
      runtime: {
        get: (workspaceId) => ({
          path: `/api/v1/workspaces/${encodeSegment(workspaceId)}/runtime`,
          query: undefined,
        }),
        retry: (workspaceId) => ({
          path: `/api/v1/workspaces/${encodeSegment(workspaceId)}/runtime/retry`,
          query: undefined,
        }),
      },
      settings: {
        get: (workspaceId) => ({
          path: `/api/v1/workspaces/${encodeSegment(workspaceId)}/settings`,
          query: undefined,
        }),
        update: (workspaceId) => ({
          path: `/api/v1/workspaces/${encodeSegment(workspaceId)}/settings`,
          query: undefined,
        }),
      },
      setup: (workspaceId) => ({
        path: `/w/${encodeSegment(workspaceId)}/setup`,
        query: undefined,
      }),
      scope: (workspaceId, subpath = '') => {
        const normalizedSubpath = normalizeWorkspaceSubpath(subpath)
        return {
          path: normalizedSubpath
            ? `/w/${encodeSegment(workspaceId)}/${normalizedSubpath}`
            : `/w/${encodeSegment(workspaceId)}/`,
          query: undefined,
        }
      },
    },
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
  uiState: {
    upsert: () => ({ path: '/api/v1/ui/state', query: undefined }),
    list: () => ({ path: '/api/v1/ui/state', query: undefined }),
    latest: () => ({ path: '/api/v1/ui/state/latest', query: undefined }),
    get: (clientId) => ({ path: `/api/v1/ui/state/${encodeSegment(clientId)}`, query: undefined }),
    delete: (clientId) => ({ path: `/api/v1/ui/state/${encodeSegment(clientId)}`, query: undefined }),
    clear: () => ({ path: '/api/v1/ui/state', query: undefined }),
    panes: {
      latest: () => ({ path: '/api/v1/ui/panes', query: undefined }),
      get: (clientId) => ({ path: `/api/v1/ui/panes/${encodeSegment(clientId)}`, query: undefined }),
    },
    focus: () => ({ path: '/api/v1/ui/focus', query: undefined }),
    commands: {
      enqueue: () => ({ path: '/api/v1/ui/commands', query: undefined }),
      next: (clientId) => ({
        path: '/api/v1/ui/commands/next',
        query: clientId ? { client_id: clientId } : undefined,
      }),
    },
  },
  github: {
    status: (workspaceId) => ({
      path: '/api/v1/auth/github/status',
      query: workspaceId ? { workspace_id: workspaceId } : undefined,
    }),
    gitProxyBase: (workspaceId) => ({
      path: workspaceId
        ? `/api/v1/auth/github/git-proxy/ws/${encodeSegment(workspaceId)}`
        : '/api/v1/auth/github/git-proxy',
      query: undefined,
    }),
    gitCredentials: (workspaceId) => ({
      path: '/api/v1/auth/github/git-credentials',
      query: workspaceId ? { workspace_id: workspaceId } : undefined,
    }),
    authorize: () => ({ path: '/api/v1/auth/github/authorize', query: undefined }),
    connect: () => ({ path: '/api/v1/auth/github/connect', query: undefined }),
    selectRepo: () => ({ path: '/api/v1/auth/github/repo', query: undefined }),
    disconnect: () => ({ path: '/api/v1/auth/github/disconnect', query: undefined }),
    installations: () => ({ path: '/api/v1/auth/github/installations', query: undefined }),
    repos: (installationId) => ({
      path: '/api/v1/auth/github/repos',
      query: { installation_id: installationId },
    }),
  },
  sessions: {
    list: () => ({ path: '/api/v1/agent/normal/sessions', query: undefined }),
    create: () => ({ path: '/api/v1/agent/normal/sessions', query: undefined }),
  },
  attachments: {
    upload: () => ({ path: '/api/v1/agent/normal/attachments', query: undefined }),
  },
  ws: {
    plugins: () => ({ path: '/ws/plugins', query: undefined }),
    pty: (query) => ({ path: '/ws/pty', query: query || undefined }),
    claudeStream: (query) => ({ path: '/ws/agent/normal/stream', query: query || undefined }),
  },
}
