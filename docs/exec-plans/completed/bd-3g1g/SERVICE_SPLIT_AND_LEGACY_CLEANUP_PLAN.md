# boring-ui Unified Service Split, Control-Plane Decoupling, and Legacy Cleanup Plan

## Goals

This is the single authoritative plan file for:

1. Service split (`front`, `workspace-core`, `pty-service`, `agent-normal`, `agent-companion`, `agent-pi`).
2. Control-plane decoupling (no feature-level coupling to gateway route schema).
3. Legacy route/code cleanup with direct cutover (no compatibility layer).
4. Frontend control-plane UX contracts for auth identity and workspace controls (sidebar user menu).

## Non-Goals (This Plan)

1. Rewriting UI feature behavior unrelated to transport/service boundaries.
2. Adding new runtime providers beyond `agent-normal`, `agent-companion`, and `agent-pi`.
3. Replacing `workspace-core` internals unless needed for boundary/policy correctness.

## Architecture Rules

1. Feature code must not hardcode control-plane patterns (for example `/w/{id}/...`).
2. Frontend networking must go through shared transport helpers only.
3. Base path/workspace prefix concerns are injected by hosting/runtime, not feature modules.
4. Companion and PI runtimes are app-domain agent services, not control-plane concerns.
5. `workspace-core` is the only owner of filesystem/git authority.
6. `pty-service` is the only owner of PTY/WebSocket terminal authority.
7. Canonical HTTP contracts follow one versioning and error-envelope policy.
8. User/session/workspace UI controls in `front` must use canonical control-plane APIs only.

## Service Boundaries

1. `front` (UI only)
2. `workspace-core` (`file`, `git`, approval/policy/authz boundary)
3. `pty-service` (terminal session lifecycle + PTY WebSocket transport)
4. `agent-normal` (native Claude stream/runtime APIs only)
5. `agent-companion` (Companion runtime/session/orchestration APIs only)
6. `agent-pi` (PI runtime/session/history/stream APIs only)

Boundary enforcement:

- Agent services do not expose independent file/git endpoint families.
- Agent services delegate file/git actions to `workspace-core` and terminal/PTY actions to `pty-service`.
- Isolation is scope/policy based (`session_id`, workspace, worktree/cwd, permissions), not endpoint duplication based.
- `workspace-core` validates capability claims for file/git actions (deny by default).
- `pty-service` validates capability claims for PTY actions (deny by default).
- Agent services can request actions but cannot bypass boundary policy checks.

## Infrastructure Ownership (Cross-Repo)

This section defines the high-level infra split across repositories so ownership is explicit.

1. `boring-ui` owns user-facing UI concerns:
   - panes/layout/components (file tree, chat, editor, sidebar user menu)
   - frontend state and interaction behavior
   - transport helper usage (`buildApiUrl`, `buildWsUrl`) from UI modules
2. `boring-sandbox` owns control-plane and gateway concerns:
   - auth/session routes (`/auth/*`)
   - control-plane API routes consumed by frontend (`/api/v1/me`, `/api/v1/workspaces`, workspace settings/runtime routes)
   - workspace onboarding route (`/w/{workspace_id}/setup`)
   - workspace-scoped proxying/routing policy (`/w/{workspace_id}/*`)
3. Runtime backend services own execution domains behind the gateway:
   - `workspace-core`: file/git authority
   - `pty-service`: terminal/PTY authority
   - agent services: runtime/session/stream orchestration
4. UI modules must not own or re-implement gateway route policy.

## Cross-Cutting API Standards

1. Versioning: canonical HTTP endpoints remain under `/api/v1/...` until explicit major bump.
2. Errors: services use one envelope (`code`, `message`, `retryable`, `details`).
3. Mutations: write/move/rename/delete define retry-safe semantics and documented conflict behavior.
4. Normative reference for envelope/code/mutation contract: `docs/exec-plans/completed/bd-3g1g/bd-3g1g.2.3-api-standards-note.md`.

## Current-State Issues

1. Mixed canonical and legacy routes still coexist.
2. Frontend callsites still include direct/legacy route patterns in some paths.
3. Runtime and workspace authority responsibilities are partially mixed.
4. Control-plane assumptions can be reintroduced unless guarded by tests/checks.

## Target Contracts

### workspace-core

- `GET /api/v1/files/list`
- `GET /api/v1/files/read`
- `PUT /api/v1/files/write`
- `DELETE /api/v1/files/delete`
- `POST /api/v1/files/rename`
- `POST /api/v1/files/move`
- `GET /api/v1/files/search`
- `GET /api/v1/git/status`
- `GET /api/v1/git/diff`
- `GET /api/v1/git/show`

### pty-service

- `WS /ws/pty`
- PTY session lifecycle endpoints (service-owned route family)

### agent-normal

- Session lifecycle + stream endpoints only.
- No direct filesystem/git mutation endpoints.

### agent-companion

- Companion-specific session/env/worktree orchestration endpoints.
- Delegates workspace operations to `workspace-core`.

### agent-pi

- PI-specific session/history/stream endpoints.
- Delegates workspace operations to `workspace-core` as needed.

### shared frontend transport

- `buildApiUrl(path, query?)`
- `buildWsUrl(path, query?)`
- Accept app-relative paths only.

### front control-plane UX contracts (auth + workspace)

- Sidebar user menu below file tree is owned by `front` UX/layout.
- Menu actions must use canonical control-plane endpoints through shared transport:
  - `GET /api/v1/me`
  - `GET /api/v1/workspaces`
  - `POST /api/v1/workspaces`
  - `GET /auth/logout`
- Workspace switching uses canonical workspace navigation (`/w/{workspace_id}/`).
- User settings in v1 are frontend-local unless/until `/api/v1/me/settings` exists.
- Detailed execution/spec lives in `docs/exec-plans/backlog/SIDEBAR_USER_MENU_PLAN.md`.

## Route Family -> Service Mapping

Interpretation:

1. This mapping defines internal service ownership, not frontend-callable URLs.
2. Frontend-callable control-plane routes are defined in `Frontend -> Control Plane Route Contract`.

1. `/api/v1/files/*` -> `workspace-core`
2. `/api/v1/git/*` -> `workspace-core`
3. `/ws/pty` and PTY session route family -> `pty-service`
4. `/api/v1/agent/normal/*` and `/ws/agent/normal/*` -> `agent-normal`
5. `/api/v1/agent/companion/*` and `/ws/agent/companion/*` -> `agent-companion`
6. `/api/v1/agent/pi/*` and `/ws/agent/pi/*` -> `agent-pi`
7. `/api/v1/me`, `/api/v1/workspaces`, `/auth/logout` -> control-plane APIs consumed by `front`

### Finalized Agent Route Prefix Contract (Phase 1)

This section is the authoritative Phase-1 decision for agent route families.

| Agent service | Canonical HTTP prefix | Canonical WebSocket prefix | Legacy/local families to rewrite |
|---|---|---|---|
| `agent-normal` | `/api/v1/agent/normal/*` | `/ws/agent/normal/*` | `/api/sessions*`, `/api/attachments`, `/ws/claude-stream` |
| `agent-companion` | `/api/v1/agent/companion/*` | `/ws/agent/companion/*` | companion service-local `/api/sessions*`, `/api/fs/*`, `/api/envs*`, `/api/git/*`, `/ws/browser/{session_id}` |
| `agent-pi` | `/api/v1/agent/pi/*` | `/ws/agent/pi/*` | PI service-local `/api/sessions*` + related stream/history lifecycle endpoints |

Hard rules:

1. Agent runtime routes must live under exactly one canonical agent prefix family.
2. New top-level agent route families outside these prefixes are not allowed.
3. Legacy/local families listed above are transitional implementation details and must be cut over to canonical agent prefixes during migration phases.

## Frontend -> Control Plane Route Contract

These are the only route families frontend product code should call directly.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/auth/login` | Public | Entry point for auth flow |
| `GET` | `/auth/callback` | Public (provider callback) | Session issuance + post-auth redirect |
| `GET` | `/auth/logout` | Session cookie | End session and return to login |
| `GET` | `/api/v1/me` | Session cookie | Current user identity for UI |
| `GET` | `/api/v1/workspaces` | Session cookie | List workspaces user can access |
| `POST` | `/api/v1/workspaces` | Session cookie | Create workspace |
| `GET` | `/api/v1/workspaces/{workspace_id}/runtime` | Session cookie + membership | Runtime status for setup/progress |
| `POST` | `/api/v1/workspaces/{workspace_id}/runtime/retry` | Session cookie + membership | Retry failed/stuck runtime provisioning |
| `GET` | `/api/v1/workspaces/{workspace_id}/settings` | Session cookie + membership | Read workspace auth/settings metadata |
| `PUT` | `/api/v1/workspaces/{workspace_id}/settings` | Session cookie + membership | Save workspace auth/settings |
| `GET` | `/w/{workspace_id}/setup` | Session cookie + membership | Onboarding/setup UX surface |
| `GET/POST/PUT/PATCH/DELETE/HEAD/OPTIONS` | `/w/{workspace_id}/{path}` | Session cookie + membership + runtime ready | Workspace-scoped HTTP proxy boundary |
| `WS` | `/w/{workspace_id}/{path}` | Session cookie + membership | Workspace-scoped WebSocket proxy boundary |

Reserved route precedence within `/w/{workspace_id}/...`:

1. Explicit control-plane routes (for example `setup`, `runtime`, `runtime/retry`, `settings`) are matched first.
2. Remaining subpaths are handled by workspace-scoped proxy routing.

### Not Frontend-Callable Directly

1. Direct service endpoints for `workspace-core`, `pty-service`, `agent-normal`, `agent-companion`, and `agent-pi`.
2. Legacy direct compat paths (`/api/*` and `/ws/*` without workspace scope).
3. Any route that bypasses control-plane auth/membership/policy checks.

## Why Control Plane Exposes This Boundary

1. Enforces auth/session and workspace membership uniformly for all UI actions.
2. Keeps one stable URL contract while backend services are split/refactored.
3. Centralizes workspace/app routing resolution and proxy policy.
4. Prevents frontend coupling to internal service topology.
5. Enables policy/audit/error handling consistency at a single boundary.

## Migration Phases

Gate policy:

1. A phase starts only when the prior phase exit gate is met.
2. A phase is complete only when its acceptance criteria are met.
3. Legacy deletion work cannot start before all dependency phase gates are green.

### Phase 0: Baseline and Mapping

1. Inventory all routes and callsites (frontend, backend, tests, docs).
2. Build mapping table: `current -> canonical -> owner`.
3. Tag each route/path as canonical, legacy, or dead.
4. Create bead tickets with dependency chain.

Entry Gate:

1. Unified plan approved by maintainers.

Exit Gate:

1. Route/callsite inventory is complete.
2. Every route has an owner and target decision.
3. Beads exist for all remaining implementation work.

Phase Acceptance Criteria:

1. Mapping file/checklist covers frontend, backend, tests, and docs callsites.
2. No route remains in an unclassified state.
3. Bead dependency order matches planned phase order.

### Phase 1: Contract Freeze

1. Freeze canonical contracts for `workspace-core`, `pty-service`, and agent services.
2. Define shared scoped context (`session_id`, `workspace_id`, `cwd/worktree`, permission claims) for both `workspace-core` and `pty-service`.
3. Publish/update API docs and examples.

Entry Gate:

1. Phase 0 exit gate is met.

Exit Gate:

1. Canonical endpoint contracts are documented and versioned.
2. Scope fields and policy expectations are defined per endpoint family.
3. Contract changes require explicit approval.

Phase Acceptance Criteria:

1. `workspace-core`, `pty-service`, `agent-normal`, `agent-companion`, and `agent-pi` contracts are frozen.
2. Error envelope is documented for all HTTP contracts.
3. Contract docs include control-plane UX endpoints used by `front`.

### Phase 2: Shared Transport Boundary

1. Standardize frontend HTTP/WS usage through shared transport helpers.
2. Remove feature-level path construction and location-derived endpoint logic.
3. Add tests to prevent reintroduction of direct/raw control-plane path use.

Entry Gate:

1. Phase 1 exit gate is met.

Exit Gate:

1. Feature networking flows through shared transport helpers.
2. Direct route construction patterns are removed from feature code.
3. Guard tests/checks exist and pass.

Phase Acceptance Criteria:

1. `buildApiUrl`/`buildWsUrl` are used by all feature callsites.
2. Static checks fail CI if direct control-plane literals are introduced.
3. Existing UI flows remain functional under canonical transport.

### Phase 2.5: Auth/User Menu Contract Alignment

1. Implement sidebar user menu placement under file tree per UX plan.
2. Wire workspace list/create/switch/logout to canonical endpoints only.
3. Validate no legacy `/api/*`/`/ws/*` fallback dependencies in menu flows.
4. Add integration coverage for menu actions and failure UX.

Entry Gate:

1. Phase 2 exit gate is met.

Exit Gate:

1. User menu actions use canonical endpoints only.
2. Workspace switch/create/logout flows are validated in tests.
3. Failure states are handled without fallback to legacy paths.

Phase Acceptance Criteria:

1. Sidebar user menu UX placement and behavior match spec.
2. Integration tests cover success and failure paths.
3. No menu code depends on legacy API route families.

### Phase 3: Workspace-Core Consolidation

1. Keep `src/back/boring_ui/api/modules/*` as source of truth for file/git APIs.
2. Remove legacy file/git handlers and route aliases.
3. Add contract tests for canonical `workspace-core` endpoints.
4. Ensure PTY ownership is moved/kept in `pty-service` only.

Entry Gate:

1. Phase 2 exit gate is met.
2. Phase 2.5 is complete, or explicitly tracked to run in parallel before Phase 5 closeout.

Exit Gate:

1. Legacy file/git handlers and aliases are removed.
2. Canonical module routers are the only backend source of truth for file/git.
3. Contract tests pass for `workspace-core`.
4. PTY route family resolves only to `pty-service`.

Phase Acceptance Criteria:

1. Backend has no reachable legacy file/git routes.
2. Canonical `workspace-core` endpoints pass contract and smoke checks.
3. Docs reflect only canonical route surfaces.

### Phase 4: Agent Runtime Separation

1. Keep `agent-normal`, `agent-companion`, and `agent-pi` as runtime-only APIs.
2. Route workspace mutations through `workspace-core` clients and PTY operations through `pty-service`.
3. Enforce policy checks at `workspace-core` and `pty-service` boundaries.
4. Add integration coverage for scoped delegation.

Entry Gate:

1. Phase 3 exit gate is met.

Exit Gate:

1. Agent services expose runtime APIs only.
2. Agent-driven workspace actions are delegated to `workspace-core` and `pty-service`.
3. Policy denials are enforced and tested at both `workspace-core` and `pty-service` boundaries.

Phase Acceptance Criteria:

1. No agent service provides independent file/git/pty endpoints.
2. Integration tests verify delegated workspace actions for all three agent services.
3. Failure-path tests verify deny-by-default behavior for invalid scope/capability requests.

### Phase 5: Cutover and Verification

1. Remove frontend fallback logic for legacy routes.
2. Delete dead backend code paths immediately after cutover validation.
3. Run unit/integration/e2e smoke for files/git/pty and all agent modes.
4. Capture verification evidence before closure.

Entry Gate:

1. Phase 4 exit gate is met.

Exit Gate:

1. Legacy fallback code is removed from frontend and backend.
2. Verification matrix tests pass.
3. Evidence is captured and linked for closeout.

Phase Acceptance Criteria:

1. No legacy route references remain in active code paths.
2. Unit/integration/e2e and UX smoke suites pass.
3. Migration closeout evidence is complete and reviewable.

## Acceptance Criteria

1. `workspace-core` is sole owner of file/git authority.
2. `pty-service` is sole owner of PTY authority.
3. Agent services expose no duplicate file/git/pty endpoint families.
4. Frontend uses canonical transport + canonical contracts only.
5. No hardcoded control-plane route schema in feature code.
6. Legacy route usage is zero and enforced by automated checks (CI when available).
7. Contracts are documented and covered by tests.
8. Sidebar user menu supports switch/create/logout on canonical contracts without legacy paths.

## Risks and Mitigations

1. Hidden legacy callsites.
   - Mitigation: static grep guard + automated fail rules (CI when available).
2. Mixed-mode migration regressions.
   - Mitigation: staged cutovers with strict smoke/integration checks.
3. Scope policy drift.
   - Mitigation: centralized policy validation in `workspace-core` and `pty-service` + contract tests.
4. Late runtime config boot timing.
   - Mitigation: explicit transport initialization gates before feature requests.

## Execution Checklist

1. Approve ownership/contract matrix.
2. Finish shared transport standardization.
3. Consolidate workspace-core modules and remove legacy routes.
4. Enforce dedicated `pty-service` ownership.
5. Migrate agent services to delegated workspace/PTY access.
6. Remove legacy fallback code paths.
7. Final verification + evidence + closeout.

## Verification Matrix

1. Static checks: no direct control-plane route literals in feature code.
2. Contract tests: canonical `workspace-core`, `pty-service`, and agent-service APIs.
3. Integration tests: delegated workspace/PTY actions from each agent service.
4. Failure-path tests: policy deny, invalid scope, and retry/error behavior.
5. Performance smoke: representative file/git, PTY, and streaming workloads.
6. UX smoke: login -> sidebar menu -> switch workspace -> create workspace -> logout.
