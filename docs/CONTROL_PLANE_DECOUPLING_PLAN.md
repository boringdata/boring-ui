# boring-ui Control-Plane Decoupling Plan

## Goal

Make `boring-ui` fully app-local with zero control-plane coupling:

- `boring-ui` owns UI + app APIs only.
- `boring-sandbox` only does auth, routing, provisioning.
- No legacy routing dependencies (`/api/*`, `/ws/*`) from frontend.

## Design Rules

1. Frontend uses one URL model only:
   - HTTP: `/w/{workspace_id}/api/...`
   - WS: `/w/{workspace_id}/ws/...`
2. Frontend resolves `workspace_id` once from location and passes it to all service clients.
3. Companion remains app-internal (Bun service), not a control-plane concern.
4. No gateway-specific branching in UI business logic.

## Scope

### In Scope

- Remove legacy path usage from frontend modules.
- Unify Files/Shell/Chat/Git clients to workspace-scoped base paths.
- Add guardrails/tests to block regressions.
- Document run/dev behavior for local + hosted modes.

### Out of Scope

- Auth/provisioning behavior inside `boring-sandbox`.
- Companion backend protocol changes.
- Major UI redesign.

## Implementation Phases

### Phase 1: Inventory + Path Mapping

1. Find all frontend uses of legacy endpoints:
   - `/api/`
   - `/ws/`
2. Map each callsite to canonical workspace-scoped equivalent.
3. Produce migration checklist by area:
   - capabilities/config
   - files
   - git
   - pty/shell
   - chat streams

### Phase 2: Shared Workspace-Aware Transport

1. Add/standardize one frontend helper for workspace-scoped URLs:
   - `buildWorkspaceApiUrl(workspaceId, path, query?)`
   - `buildWorkspaceWsUrl(workspaceId, path, query?)`
2. Route all panel/service clients through these helpers.
3. Ensure helpers are mode-safe (local + hosted) without control-plane assumptions.

### Phase 3: Feature Migration

1. Files panel and file service calls -> `/w/{id}/api/v1/files/...`
2. Shell/PTy -> `/w/{id}/ws/pty`
3. Chat/code sessions -> `/w/{id}/ws/claude-stream` and corresponding API reads
4. Git + config + capabilities -> `/w/{id}/api/...` equivalents

### Phase 4: Remove Legacy Dependencies

1. Remove frontend fallback calls to plain `/api/*` and `/ws/*`.
2. Add strict runtime warning/error if a legacy route is attempted.
3. Coordinate with `boring-sandbox` to remove compat router after UI release is verified.

### Phase 5: Test + Rollout

1. Unit tests for URL builders and workspace extraction.
2. Integration/E2E assertions:
   - no network calls to `/api/*` or `/ws/*` without workspace prefix
   - Files/Shell/Code Sessions all green in hosted mode
3. Staged rollout:
   - dev validation
   - hosted smoke test
   - compat removal in gateway

## Acceptance Criteria

1. Frontend makes zero legacy route calls (`/api/*`, `/ws/*`) during normal workspace usage.
2. Files, Shell, Code Sessions, Git all work via workspace-scoped paths only.
3. Companion integration still works as app-internal service.
4. Gateway compat route can be removed with no user-facing regression.

## Risks and Mitigations

1. Risk: hidden legacy callsites in older hooks/components.
   - Mitigation: grep + network-level test assertion in E2E.
2. Risk: workspace ID unavailable early in bootstrap.
   - Mitigation: explicit loading state and deferred client init.
3. Risk: partial migration causes mixed routing.
   - Mitigation: fail-fast lint/test rule for legacy path strings.

## Suggested Task Breakdown (Beads)

1. Inventory + callsite map.
2. Shared workspace URL helper.
3. Files + git migration.
4. Shell + chat WS migration.
5. Legacy route blocker tests.
6. Hosted smoke + gateway compat removal handoff.

