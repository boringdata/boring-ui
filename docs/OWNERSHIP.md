# Route Ownership Audit

This document defines which routes belong to the boring-ui core framework and which are extensible by child apps.

## Extension Model

Child apps extend boring-ui through **tRPC routers** declared in `boring.app.toml [backend].routers`. They cannot override or shadow core routes. Frontend extension is through the **pane registry** with capability gating.

## Core Routes (Do Not Modify in Child Apps)

| Route Group | Pattern | Description |
|-------------|---------|-------------|
| Health | `/health`, `/healthz` | Service health checks |
| Config | `/__bui/config`, `/api/config`, `/api/capabilities` | Runtime config and feature discovery |
| Auth | `/auth/login`, `/auth/logout`, `/auth/settings` | Session management |
| User | `/api/v1/me`, `/api/v1/me/settings` | User identity and settings |
| Workspaces | `/api/v1/workspaces/*` | Workspace CRUD, runtime, settings |
| Collaboration | `/api/v1/workspaces/{id}/members*`, `/api/v1/workspaces/{id}/invites*` | Member RBAC, invitations |
| Files | `/api/v1/files/*` | File read/write/list/search/rename/move |
| Git | `/api/v1/git/*` | Status, diff, commit, push, pull, branch, merge |
| Exec | `/api/v1/exec/*` | Command execution (sync + async jobs) |
| UI State | `/api/v1/ui/*` | Panel layout, focus, command queue |
| GitHub | `/api/v1/auth/github/*` | OAuth, App installations, credentials |
| Agent (PI) | `/api/v1/agent/pi/*` | PI agent sessions and streaming |
| Agent (AI SDK) | `/api/v1/agent/chat` | Claude AI SDK integration |
| Workspace Boundary | `/w/{workspaceId}/*` | Workspace-scoped routing proxy |
| Static / SPA | `/`, `/*` | Frontend assets and SPA fallback |

## Child-App Extensible Routes

| Extension Point | Mechanism | Configuration |
|-----------------|-----------|---------------|
| tRPC Routers | `POST /trpc/{namespace}.*` | `boring.app.toml [backend].routers` |
| Custom Panels | Pane registry with capability gating | `boring.app.toml [frontend.panels]` |
| Agent Tools | Tool registration in router context | Export from tRPC router module |
| Workspace Settings | Per-workspace key-value store | `PUT /api/v1/workspaces/{id}/settings` |

### How Child Apps Add Routes

```toml
# boring.app.toml
[backend]
routers = ["src/server/routers/analytics:analyticsRouter"]
```

```typescript
// src/server/routers/analytics.ts
export const analyticsRouter = fw.router({
  pageViews: fw.workspaceProcedure.query(() => 42),
});
// Accessible as: POST /trpc/analytics.pageViews
```

### Rules

1. Child apps **cannot** redefine core routes
2. Child apps **cannot** add raw HTTP routes — tRPC only
3. All child procedures receive workspace auth context automatically
4. Frontend panes declare `requiresRouters` for capability gating
5. Capabilities endpoint (`/api/capabilities`) reports available routers

## Registered Child Apps

From `children.toml`:

| App | Repository |
|-----|-----------|
| boring-macro | boringdata/boring-macro |
| boring-content | boringdata/boring-de-nl |
| bdocs | boringdata/boring-docs |
| boring-doctor | hachej/boring-doctor |
