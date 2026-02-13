# Feature 3 Plan (V0): External Control Plane, Onboarding, Workspaces, and MCP

## 1. Executive Summary
V0 ships a fast, practical multi-workspace platform with:
1. Supabase auth and workspace membership.
2. Modal-hosted control plane (FastAPI + async jobs).
3. Sprite-hosted private workspace runtime.
4. MCP/agent usage is available to any authenticated member of the active workspace.

Primary objective: perfect user onboarding and workspace lifecycle first, with minimal infra complexity.

## 1.1 Tooling Plan (CLI)
This implementation is operated with:
1. `modal` CLI
- deploy and manage control-plane service
- run/manage provisioning jobs
- manage artifact volume workflows

2. `supabase` CLI
- manage and apply schema migrations
- manage local/dev auth + database configuration workflows

3. `sprite` CLI
- inspect/manage workspace sandbox runtime
- support runtime diagnostics during provisioning and operations

## 2. Scope
### 2.1 In Scope (V0)
1. Login/signup, first workspace creation, provisioning, invite acceptance.
2. Workspace list, switcher, settings page, membership-based permissions.
3. One workspace sandbox runtime in Sprite.
4. Shared workspace folder runtime model (no per-session filesystem isolation yet).
5. Control plane orchestrates provisioning jobs via Modal.

### 2.2 Out of Scope (V0)
1. Workspace suspend/resume/delete lifecycle controls.
2. Per-session worktree/jail isolation.
3. Anonymous share links.
4. Multi-provider runtime abstraction beyond Sprite.

## 3. Locked Decisions (V0)
1. Control plane runs on Modal.
2. Runtime sandbox provider is Sprite.
3. Auth + metadata store is Supabase.
4. Control plane uses a static server-side Sprite bearer token from Modal secrets.
5. Browser never receives sandbox credentials.
6. Share links require authenticated session.
7. Share link default expiry is 24h (override allowed).
8. Single membership role is `admin` (all workspace members are admins in V0).
9. Any workspace member (`admin`) can create share links.
10. Workspace switching is hard navigation on `/w/{workspace_id}/...`.
11. Provisioning failures must show explicit Retry action in UI.
12. `session_id` is part of API context in V0 (optional), and becomes required in future isolation modes.
13. Frontend and backend are co-hosted inside each workspace sandbox in V0.
14. Login UI is one shared standard page in V0 with only app branding params: `name`, `logo`.
15. Workspaces are app-scoped via `app_id`; runtime artifacts are resolved by `app_id` + `release_id`.
16. Sprite sandbox naming is deterministic: `sbx-{app_id}-{workspace_id}-{env}`.

## 4. Target User Workflow (V0)
```text
[Open app]
   |
   v
[Authenticated?] --no--> [Login/Signup] --> [Session created]
   |                                         |
  yes                                        v
   |                                  [Load workspaces]
   v                                         |
[Has workspace membership?] --no--> [Onboarding: Create workspace]
   |                                           |
  yes                                          v
   |                                   [Provisioning starts]
   |                                           |
   |                                   [Ready or Error+Retry]
   |                                           |
   +-------------------------------> [Enter /w/{workspace_id}/app]
                                               |
                                               v
                                  [Agent session + MCP tools]
                                               |
                                               v
                                  [Switch workspace anytime]

Invite path:
[Admin invites email] -> [Pending invite] -> [Invitee logs in]
-> [Auto-accept by email match] -> [Workspace appears in list]
```

## 5. Architecture
### 5.1 System Overview
```text
User Browser
   |
   v
Public App Endpoint (Control Plane domain)
   | \
   |  \--(workspace resolve + authz)--> Control Plane API (FastAPI on Modal)
   |                                       | \
   |                                       |  \--> Supabase (Auth + Postgres)
   |                                       |
   |                                       \--> Modal Provisioning Job
   |                                               | \
   |                                               |  \--> Modal Volume (artifacts)
   |                                               \--> Sprite Runtime API
   |                                                       |
   \------------------ proxied UI/API traffic -----------> Workspace Sandbox (Sprite)
```

### 5.2 Two Planes
1. Control plane (public): auth, onboarding, workspace governance, provisioning orchestration, private proxy.
2. Workspace plane (private): co-hosted frontend+backend runtime for files/git/pty/chat/agent execution per workspace.
3. Route ownership:
- control plane owns global/auth routes (`/auth/*`, `/api/v1/workspaces*`, `/api/v1/me`, session selection).
- workspace plane owns workspace app/runtime routes under `/w/{workspace_id}/...`.

### 5.3 Routing Contract Table
| Route pattern | Served by | Notes |
|---|---|---|
| `/auth/*` | Control plane | Supabase login/callback/session setup |
| `/api/v1/app-config` | Control plane | app branding/config by host and app_id |
| `/api/v1/me` | Control plane | user/session info |
| `/api/v1/workspaces*` | Control plane | workspace CRUD/members/runtime status |
| `/api/v1/session/workspace` | Control plane | active workspace selection |
| `/w/{workspace_id}/app*` | Workspace plane | co-hosted frontend assets/pages |
| `/w/{workspace_id}/api/v1/files*` | Workspace plane (proxied) | file operations |
| `/w/{workspace_id}/api/v1/git*` | Workspace plane (proxied) | git operations |
| `/w/{workspace_id}/api/v1/pty*` | Workspace plane (proxied) | terminal/PTY |
| `/w/{workspace_id}/api/v1/agent/sessions*` | Workspace plane (proxied) | agent stream/input/stop |

## 6. Repository Structure (Target)
```text
boring-ui/
  src/
    app/
      back/
        api/
          app.py
          modules/
            files/
            git/
            pty/
            stream/
      front/
        App.jsx
        main.jsx
        components/
        panels/
      scripts/
        build_release_bundle.sh
      deploy/
        sprite/
          bootstrap.sh
          runtime.env.example
        modal/
          deploy_release.py
    control_plane/
      app/
        main.py
        middleware/
        routes/
          auth.py
          workspaces.py
          members.py
          sessions.py
          provisioning.py
        services/
          auth_service.py
          workspace_service.py
          provisioning_service.py
          runtime_proxy_service.py
        providers/
          sprite_provider.py
        models/
          schemas.py
      migrations/
      modal/
        modal_app.py
        jobs/
          provision_workspace.py
        artifacts/
          publish_release.py
  docs/ideas/
    feature-3-external-control-plane-with-auth.md
```

Migration sequence (from current repo layout):
1. move frontend from `src/front/*` to `src/app/front/*`.
2. move backend API from `src/back/*` to `src/app/back/*`.
3. introduce `src/control_plane/*` without breaking existing runtime app boot.
4. switch CI/build script paths after move is complete.

## 7. Runtime Responsibilities by Operation
1. Files:
- backend: `src/app/back/api/modules/files/*`
- frontend: `src/app/front/components/FileTree.jsx`, `src/app/front/components/Editor.jsx`

2. Git:
- backend: `src/app/back/api/modules/git/*`
- frontend: `src/app/front/components/GitChangesView.jsx`, `src/app/front/components/GitDiff.jsx`

3. Terminal/exec (PTY):
- backend: `src/app/back/api/modules/pty/*`, `src/app/back/api/pty_bridge.py`
- frontend: `src/app/front/components/Terminal.jsx`, `src/app/front/panels/ShellTerminalPanel.jsx`

4. Chat/agent stream:
- backend: `src/app/back/api/modules/stream/*`, `src/app/back/api/stream_bridge.py`
- frontend: `src/app/front/components/chat/ClaudeStreamChat.jsx`, `src/app/front/components/chat/ChatPanel.jsx`

5. MCP behavior (through agent stream path):
- backend enforcement/bridge: `src/app/back/api/stream_bridge.py`
- frontend command surface: `src/app/front/components/chat/ClaudeStreamChat.jsx`

## 8. Build, Publish, and Deploy
### 8.1 Build and Package (Local or CI)
Canonical builder script:
- `src/app/scripts/build_release_bundle.sh`

Outputs:
1. `dist/` (frontend build)
2. `boring_ui-*.whl` (backend wheel)
3. `bundle.tar.gz`
4. `manifest.json`
5. `bundle.tar.gz.sha256`

### 8.2 Artifact Storage
Artifacts are stored in Modal Volume:
- `/mnt/artifacts/{app_id}/{release_id}/bundle.tar.gz`
- `/mnt/artifacts/{app_id}/{release_id}/manifest.json`
- `/mnt/artifacts/{app_id}/{release_id}/bundle.tar.gz.sha256`

### 8.3 Provisioning Deploy (Modal Job -> Sprite)
Provisioning is deployment-only (no build):
1. Resolve `app_id` and `release_id` from workspace runtime metadata.
2. Pull bundle from Modal Volume for `{app_id}/{release_id}`.
3. Verify `bundle.tar.gz` checksum against `bundle.tar.gz.sha256`.
4. Copy/unpack into Sprite sandbox.
5. Run `src/app/deploy/sprite/bootstrap.sh`.
6. Run health checks.
7. Mark runtime `ready` or `error`.

### 8.4 Release Selection and Availability Contract
1. Workspace creation must resolve an immutable `release_id` before provisioning is queued.
2. Create request may pass explicit `release_id`; when omitted, control plane resolves the app default release for `app_id`.
3. If artifacts for resolved `{app_id, release_id}` are missing, API returns `503 release_unavailable` and does not enqueue provisioning.
4. Control plane persists resolved `release_id` and `bundle_sha256` on runtime metadata for audit/debug correlation.

### 8.5 Sandbox Naming Contract
1. Control plane computes Sprite sandbox name as `sbx-{app_id}-{workspace_id}-{env}`.
2. `env` is resolved from control-plane environment (for example: `dev`, `staging`, `prod`) and must be stable per deployment target.
3. `app_id`, `workspace_id`, and `env` are normalized to lowercase slug-safe tokens before name assembly.
4. Control plane persists computed `sandbox_name` in runtime metadata and returns it from runtime/provisioning APIs for diagnostics.

## 9. Provisioning Contract
### 9.1 API Endpoints
1. `POST /api/v1/workspaces`
- Creates workspace metadata and enqueues provisioning.
- Returns `202` with `workspace_id`, `provision_job_id`, `runtime_state=provisioning`.
- Returns `503 release_unavailable` and does not enqueue when no valid release can be resolved.

2. `GET /api/v1/workspaces/{id}/runtime`
- Returns current runtime state, step, attempt, last error.

3. `POST /api/v1/workspaces/{id}/retry`
- Workspace member explicit retry (all members are `admin` in V0).
- Returns `202` and new/continued provisioning context.

4. Optional `GET /api/v1/workspaces/{id}/events`
- SSE status stream (polling fallback remains supported).

### 9.2 Provisioning State Machine
```text
queued
  -> release_resolve
  -> creating_sandbox
  -> uploading_artifact
  -> bootstrapping
  -> health_check
  -> ready

any step -> error
error --(explicit retry)--> queued
```

Idempotency/concurrency safeguards (V0 minimum):
1. At most one active provisioning job per workspace at a time.
2. Create/retry endpoints require `idempotency_key` and dedupe retried client requests server-side.
3. Retry defaults:
- max automatic retries per job: `2`
- backoff: `2s`, then `6s`
- step timeout defaults:
  - `release_resolve`: `15s`
  - `creating_sandbox`: `60s`
  - `uploading_artifact`: `60s`
  - `bootstrapping`: `120s`
  - `health_check`: `30s`
4. Jobs exceeding step timeout move to `error` with `last_error_code=STEP_TIMEOUT`.

### 9.3 Job Tracking Table
`cloud.workspace_provision_jobs` fields:
1. `id`, `workspace_id`, `state`, `attempt`, `modal_call_id`
2. `started_at`, `finished_at`
3. `last_error_code`, `last_error_detail`
4. `request_id`, `idempotency_key`, `created_by`, `created_at`, `updated_at`

## 10. Onboarding and Workspace UX Contract
### 10.1 User States
1. `unauthenticated`
2. `authenticated_no_workspace`
3. `workspace_selected_provisioning`
4. `workspace_selected_ready`
5. `workspace_selected_error`

### 10.2 Required Frontend Surfaces
1. `/app/settings`
2. `/app/workspaces`
3. global workspace switcher on authenticated pages

### 10.3 Workspace URL Model
- `https://app.example.com/w/{workspace_id}/...`

Examples:
- `/w/ws_123/app`
- `/w/ws_123/api/v1/files/list`

### 10.4 Role Expectations
1. V0 uses one role only: `admin`.
2. Any workspace member can manage members and edit content.

## 11. Control Plane API Surface (V0)
1. `POST /auth/login`
2. `GET /auth/callback`
3. `GET /api/v1/me`
4. `GET /api/v1/workspaces`
5. `POST /api/v1/workspaces`
6. `GET /api/v1/workspaces/{id}`
7. `PATCH /api/v1/workspaces/{id}`
8. `POST /api/v1/workspaces/{id}/members`
9. `GET /api/v1/workspaces/{id}/members`
10. `DELETE /api/v1/workspaces/{id}/members/{member_id}`
11. `POST /api/v1/session/workspace`
12. `GET /api/v1/workspaces/{id}/runtime`
13. `POST /api/v1/workspaces/{id}/retry`
14. `POST /api/v1/workspaces/{id}/shares`
15. `GET /api/v1/shares/{token}`
16. `PUT /api/v1/shares/{token}`
17. `DELETE /api/v1/workspaces/{id}/shares/{share_id}`
18. `GET /api/v1/app-config`

Session context rule for workspace-scoped routes:
1. Accept optional `X-Session-ID` header in V0.
2. If missing, control plane may use/create a default session context.
3. Persist `session_id` in logs/audit for stream correlation.
4. Require/generate `X-Request-ID` for every request and propagate it to runtime.
5. Workspace resolution precedence:
- first: workspace id from URL path (`/w/{workspace_id}/...`)
- second: `X-Workspace-ID` header (only on endpoints that allow it)
- third: active workspace in user session
6. Conflict rule:
- if multiple sources are provided and mismatch, return `400 workspace_context_mismatch`.

### 11.1 Endpoint Schemas and Error Codes (V0)
1. `POST /api/v1/workspaces`
Request:
```json
{
  "name": "Acme Workspace",
  "app_id": "boring-ui",
  "release_id": "2026-02-13.1",
  "sandbox_profile": "standard",
  "idempotency_key": "req-create-ws-001"
}
```
Response `202`:
```json
{
  "workspace_id": "ws_123",
  "app_id": "boring-ui",
  "release_id": "2026-02-13.1",
  "sandbox_name": "sbx-boring-ui-ws-123-prod",
  "runtime_state": "provisioning",
  "provision_job_id": "job_456",
  "request_id": "req_01H..."
}
```
Errors: `400 invalid_request|missing_idempotency_key`, `401 unauthorized`, `409 workspace_exists`, `503 release_unavailable`.

2. `GET /api/v1/workspaces/{id}/runtime`
Response `200`:
```json
{
  "workspace_id": "ws_123",
  "state": "provisioning",
  "step": "bootstrapping",
  "attempt": 1,
  "release_id": "2026-02-13.1",
  "sandbox_name": "sbx-boring-ui-ws-123-prod",
  "last_error_code": null,
  "last_error_detail": null,
  "updated_at": "2026-02-13T10:00:00Z"
}
```
Errors: `401 unauthorized`, `403 forbidden`, `404 workspace_not_found`.

3. `POST /api/v1/workspaces/{id}/retry`
Request:
```json
{
  "idempotency_key": "req-retry-ws-001"
}
```
Response `202`:
```json
{
  "workspace_id": "ws_123",
  "release_id": "2026-02-13.1",
  "sandbox_name": "sbx-boring-ui-ws-123-prod",
  "runtime_state": "provisioning",
  "provision_job_id": "job_789"
}
```
Errors: `400 missing_idempotency_key`, `401 unauthorized`, `403 forbidden`, `404 workspace_not_found`, `409 provisioning_in_progress`, `503 release_unavailable`.

4. `POST /api/v1/session/workspace`
Request:
```json
{
  "workspace_id": "ws_123"
}
```
Response `200`:
```json
{
  "workspace_id": "ws_123",
  "role": "admin",
  "runtime_state": "ready",
  "next_path": "/w/ws_123/app"
}
```
Errors: `401 unauthorized`, `403 forbidden`, `404 workspace_not_found`.

5. `POST /api/v1/workspaces/{id}/members`
Request:
```json
{
  "email": "user@example.com",
  "role": "admin"
}
```
Response `201`:
```json
{
  "workspace_id": "ws_123",
  "email": "user@example.com",
  "role": "admin",
  "status": "pending"
}
```
Errors: `400 invalid_email`, `401 unauthorized`, `403 forbidden`, `409 duplicate_invite`.

6. `POST /api/v1/workspaces/{id}/shares`
Request:
```json
{
  "path": "/docs/README.md",
  "access": "read",
  "expires_in_hours": 24
}
```
Response `201`:
```json
{
  "share_id": "shr_123",
  "token": "opaque-token",
  "access": "read",
  "expires_at": "2026-02-14T10:00:00Z"
}
```
Errors: `400 invalid_path`, `401 unauthorized`, `403 forbidden`.

7. `GET /api/v1/shares/{token}`
Response `200`:
```json
{
  "workspace_id": "ws_123",
  "path": "/docs/README.md",
  "content": "...",
  "access": "read"
}
```
Errors: `401 unauthorized`, `403 share_scope_violation`, `404 share_not_found`, `410 share_expired`.

8. `PUT /api/v1/shares/{token}`
Request:
```json
{
  "path": "/docs/README.md",
  "content": "updated"
}
```
Response `200`:
```json
{
  "status": "ok"
}
```
Errors: `401 unauthorized`, `403 share_scope_violation`, `404 share_not_found`, `410 share_expired`.

9. `GET /api/v1/app-config`
Response `200`:
```json
{
  "app_id": "boring-ui",
  "name": "Boring UI",
  "logo": "/assets/boring-ui-logo.svg",
  "default_release_id": "2026-02-13.1"
}
```
Errors: `400 app_context_mismatch`, `404 app_config_not_found`.

## 12. Supabase Data Model (V0)
Core tables:
1. `cloud.workspaces`
2. `cloud.workspace_members`
3. `cloud.workspace_runtime`
4. `cloud.workspace_provision_jobs`
5. `cloud.audit_events`
6. `cloud.file_share_links`

Key constraints:
1. exactly one runtime row per workspace.
2. membership role in (`admin`) only for V0.
3. runtime state in (`provisioning`,`ready`,`error`).
4. workspace and runtime are app-scoped (`app_id` required).
5. runtime row persists immutable deployment selectors (`release_id`, `bundle_sha256`) per provisioning attempt.
6. runtime row persists deterministic sandbox identity (`sandbox_name`) using `sbx-{app_id}-{workspace_id}-{env}` convention.
7. share-link `access` in (`read`,`write`) with token hash only.
8. share-link scope is exact-path only in V0 (`path` is normalized absolute workspace-relative path).
9. reject share-link access when normalized request path does not exactly match link path.

RLS baseline:
1. members can read their workspace records.
2. active workspace membership (`admin` in V0) required for membership mutation.
3. provisioning/internal mutations via service role.

Audit baseline (`cloud.audit_events`) required fields:
1. `workspace_id`
2. `user_id` (nullable for system actor)
3. `action`
4. `request_id`
5. `payload` (json)
6. `created_at`

### 12.1 SQL DDL Additions for V0 Guarantees
```sql
-- Provisioning idempotency
alter table cloud.workspace_provision_jobs
  add column if not exists idempotency_key text;

create unique index if not exists ux_workspace_jobs_active
  on cloud.workspace_provision_jobs(workspace_id)
  where state in ('queued','release_resolve','creating_sandbox','uploading_artifact','bootstrapping','health_check');

-- Optional dedupe on client idempotency key
create unique index if not exists ux_workspace_jobs_idempotency
  on cloud.workspace_provision_jobs(workspace_id, idempotency_key)
  where idempotency_key is not null;

-- Share-link scope constraints
alter table cloud.file_share_links
  add column if not exists access text check (access in ('read','write')),
  add column if not exists revoked_at timestamptz;

create index if not exists ix_file_share_links_workspace_path
  on cloud.file_share_links(workspace_id, path);

-- Audit request correlation
create index if not exists ix_audit_events_workspace_request
  on cloud.audit_events(workspace_id, request_id, created_at desc);

-- App scoping
alter table cloud.workspaces
  add column if not exists app_id text not null default 'boring-ui';

alter table cloud.workspace_runtime
  add column if not exists app_id text not null default 'boring-ui',
  add column if not exists release_id text,
  add column if not exists sandbox_name text,
  add column if not exists bundle_sha256 text;

create index if not exists ix_workspaces_app_id on cloud.workspaces(app_id);
create index if not exists ix_workspace_runtime_app_id on cloud.workspace_runtime(app_id);
create index if not exists ix_workspace_runtime_app_release on cloud.workspace_runtime(app_id, release_id);
create index if not exists ix_workspace_runtime_sandbox_name on cloud.workspace_runtime(sandbox_name);
```

## 13. Auth and Authorization Model
### 13.0 Supabase Auth Mode (Locked for V0)
1. Provider: Supabase Auth.
2. Web login mode: email magic link (default), OAuth providers optional.
3. Callback endpoint: `GET /auth/callback`.
4. Identity source of truth: `auth.users.id` (UUID) + normalized email.
5. Login page mode: standard shared login template only (no custom component mode in V0).
6. App-level login branding parameters:
- `name` (display name)
- `logo` (logo URL or asset path)
7. Login branding source and precedence:
- first: `cloud.workspace_runtime.config.login_branding` (if workspace context exists)
- second: app default config from control-plane environment
- third: hardcoded fallback (`name="App"`, default logo)
8. `app_id` resolution and validation:
- first: request host/domain mapping -> `app_id`
- second: for workspace-scoped routes, validate resolved `app_id` matches workspace `app_id`
- mismatch result: `400 app_context_mismatch`

### 13.1 Browser Auth
1. Browser completes Supabase auth and returns via `/auth/callback`.
2. Control plane verifies Supabase access token using JWKS (audience `authenticated`).
3. Control plane establishes secure HTTP-only session cookie for app requests.
4. Browser calls control-plane APIs only (never direct sandbox auth).

Session/cookie requirements:
1. `HttpOnly=true`
2. `Secure=true` (except explicit local-dev override)
3. `SameSite=Lax`
4. bounded TTL with rolling refresh

Accepted auth transport:
1. Browser: session cookie.
2. CLI/internal callers: `Authorization: Bearer <supabase_access_token>`.

### 13.2 Runtime Access
1. Control plane performs user/workspace membership checks.
2. Control plane proxies runtime calls privately.
3. Control plane injects Sprite bearer token server-side.
4. Control plane propagates `session_id` (when present) to runtime handlers for correlation and future isolation compatibility.
5. V0 token boundary:
- the same static Sprite bearer may be used for runtime management and proxied runtime requests.
- token never leaves server-side control plane.
- rotate token via Modal secrets and restart control-plane processes.

### 13.3 Security Boundary
1. workspace plane does not trust browser identity.
2. workspace plane accepts only control-plane proxied requests with valid server-side bearer.

### 13.4 Invite/Auth Identity Match Rule
1. Invite auto-accept runs on first authenticated `GET /api/v1/workspaces` after login, using case-insensitive email match.
2. Membership activation binds to `auth.users.id` after first successful login.
3. Invite lifecycle defaults:
- duplicate pending invite for same `(workspace_id,email)` is rejected with `409`.
- re-invite is allowed only after prior invite/member is removed.
- member removal sets membership status to `removed` (soft removal), not hard delete in V0.

## 14. MCP Integration Contract (V0)
### 14.1 Scope
1. MCP execution occurs inside workspace sandbox runtime.
2. Browser never calls MCP servers directly.
3. Control plane validates authenticated workspace membership before proxying MCP/agent operations.

### 14.2 Session API
1. `POST /w/{workspace_id}/api/v1/agent/sessions`
2. `GET /w/{workspace_id}/api/v1/agent/sessions/{session_id}/stream`
3. `POST /w/{workspace_id}/api/v1/agent/sessions/{session_id}/input`
4. `POST /w/{workspace_id}/api/v1/agent/sessions/{session_id}/stop`

Session ID contract:
1. V0: `session_id` is optional for non-agent workspace APIs.
2. V0: `session_id` is required for agent stream lifecycle endpoints.
3. V1+: `session_id` becomes required for all workspace-mutating operations.

## 15. Imported Patterns (from kurt-cloud, adapted)
1. Middleware allowlist + JWT decode + request context.
2. Thin HTTP routes delegating to service layer.
3. Auto-accept pending invites on workspace list load.
4. Service-layer membership checks for mutations.
5. Async provisioning side effects (never block create request).
6. Explicit provisioning state transitions for UX and retries.

## 16. CLI Tooling Contract
V0 deploy/manage commands must be operable with:
1. `modal` CLI
- deploy control plane and provisioning jobs
- manage Modal app/function lifecycle

2. `sprite` CLI
- inspect/manage workspace sandbox runtime
- diagnostics and runtime verification

3. `supabase` CLI
- apply migrations
- manage local/dev schema and auth config workflows

Non-goal:
- required manual cloud-console steps for normal deploy should be avoided.

## 17. Risks
1. Shared workspace folder can cause concurrent edit conflicts.
2. Proxy misconfiguration can break WS/SSE behavior.
3. Provisioning races can create partial runtime states without strict idempotency.
4. Missing service-layer membership checks can create tenant boundary bugs.
5. Artifact checksum/manifest mismatch can block deploys without clear operator guidance.
6. Stale Sprite bearer secret can cause widespread runtime auth failures.
7. `app_id` host mapping mistakes can serve wrong branding/config.
8. Missing stale-job cleanup can leave workspaces stuck in `provisioning`.

### 17.1 Operational Controls and Runbooks (V0 minimum)
1. Provisioning stuck-state control:
- detector: job state not changing past step timeout.
- action: transition job to `error`, set `last_error_code=STEP_TIMEOUT`, expose retry.
2. Artifact integrity failure control:
- detector: checksum mismatch during deploy.
- action: set `last_error_code=ARTIFACT_CHECKSUM_MISMATCH`, block rollout, notify operator.
3. Secret rotation control:
- detector: auth failures spike after token rotation window.
- action: rotate Modal secret, restart control-plane workers, re-run health checks.
4. App mapping control:
- detector: `app_context_mismatch` errors above baseline.
- action: verify host->app_id mapping config and workspace `app_id` metadata alignment.

### 17.2 On-Call Signals, SLOs, and Escalation
1. API availability SLO:
- target: `99.5%` monthly for control-plane auth/workspace APIs.
- alert: 5m error rate (`5xx`) > `2%` for `/api/v1/workspaces*` or `/auth/callback`.
2. Provisioning reliability SLO:
- target: `>= 99%` successful provisioning for valid releases.
- alert: 15m failure rate (`state=error`) > `5%` grouped by `last_error_code`.
3. Tenant-isolation safety signal:
- alert immediately on any confirmed cross-workspace access event (severity `SEV-1`).
- mandatory action: freeze rollout, rotate affected credentials, publish incident summary.
4. Escalation owner model:
- control-plane/API failures: on-call backend owner.
- Supabase auth/RLS failures: database/platform owner.
- Sprite runtime/proxy failures: runtime owner.

## 18. Acceptance Criteria (V0, gate-ready and measurable)
### 18.1 Auth and Session
1. `GET /auth/callback` success sets session cookie with `HttpOnly=true`, `Secure=true` (except explicit local-dev override), and `SameSite=Lax`.
2. `GET /api/v1/me` returns `200` with stable user identity fields (`user_id`, `email`) for an authenticated session.
3. Invalid/expired auth input returns `401 unauthorized` without creating a valid app session.
4. Unauthenticated calls to workspace or share endpoints return `401` (not `500`).

### 18.2 Invites and Membership
1. `POST /api/v1/workspaces/{id}/members` creates `pending` invite membership for valid email.
2. First authenticated workspace-list load for matching email auto-activates pending invite.
3. Duplicate pending invite for same `(workspace_id,email)` returns `409 duplicate_invite`.
4. Removed/non-member users receive `403 forbidden` for workspace-scoped APIs.

### 18.3 Provisioning and Release Selection
1. `POST /api/v1/workspaces` returns `202` with `workspace_id`, `provision_job_id`, `release_id`, and `request_id`.
2. If release artifacts are unavailable, create/retry returns `503 release_unavailable` and no new active job is created.
3. Concurrent create/retry calls for the same workspace preserve single-active-job invariant and idempotent response behavior.
4. Timeout/checksum failures transition runtime state to `error` with explicit `last_error_code` values (`STEP_TIMEOUT`, `ARTIFACT_CHECKSUM_MISMATCH`).
5. Explicit retry from `error` creates/continues a new provisioning attempt and preserves audit correlation.
6. `sandbox_name` is deterministic and equals `sbx-{app_id}-{workspace_id}-{env}` across create/runtime/retry responses.

### 18.4 Proxy and Routing
1. Control-plane and workspace-plane routing behavior matches section 5.3 exactly.
2. Workspace context conflicts return `400 workspace_context_mismatch`.
3. `X-Request-ID` is generated/accepted by control plane and propagated unchanged to runtime logs.
4. SSE and WS/stream proxy paths sustain active sessions and close upstream cleanly on client disconnect.

### 18.5 MCP and Agent Sessions
1. `POST /w/{workspace_id}/api/v1/agent/sessions` and session lifecycle endpoints are member-only.
2. `session_id` is required on stream/input/stop endpoints.
3. Non-member access is denied with `403 forbidden`.
4. Duplicate stop calls are idempotent and do not leave orphan runtime processes.

### 18.6 Share Links
1. Share-link read/write endpoints require authenticated session.
2. Path access is normalized and exact-path scoped; traversal or non-matching paths are denied.
3. Expired links return `410 share_expired`; revoked/unknown links return `404 share_not_found`.
4. Only token hash is persisted; plaintext share token is never written to persistent logs.

### 18.7 App Identity and Config Resolution
1. Host -> `app_id` resolution is deterministic and mismatch yields `400 app_context_mismatch`.
2. `GET /api/v1/app-config` returns `app_id`, `name`, `logo`, and `default_release_id`.
3. Runtime metadata for provisioned workspaces records `app_id`, `release_id`, and `bundle_sha256`.
4. Runtime metadata includes `sandbox_name` computed from `sbx-{app_id}-{workspace_id}-{env}`.

### 18.8 Observability and Audit
1. All mutating control-plane endpoints emit `cloud.audit_events` entries with required fields from section 12.
2. Provisioning failures include actionable error code/detail visible via runtime status API.
3. Alerts defined in section 17.2 are wired before production rollout.
4. Sprite bearer credentials never appear in browser responses or audit payloads.

## 19. Implementation Order and Dependencies
### 19.1 External Prerequisites (blocking dependencies)
1. `P1` Release artifacts published for target `{app_id, release_id}` with checksum and manifest.
2. `P2` Modal secrets configured and validated (`SPRITE_BEARER_TOKEN`, Supabase keys/JWKS settings).
3. `P3` Public host + TLS + Supabase callback URL aligned for target environment.
4. `P4` Log/metrics sink and alert routing configured for control-plane and provisioning jobs.
5. `P5` Supabase RLS/service-role permissions reviewed for tenant boundary and least privilege.

### 19.2 Epic Order (dependency-complete)
1. Epic A: Supabase schema + migrations.
- depends on: `P5`.
- blocks: all stateful epics.
2. Epic B: Auth/session middleware + `/api/v1/me`.
- depends on: A, `P2`, `P3`.
- blocks: C, D, E, F, G, H, I.
3. Epic I: App identity/config resolution (`app_id`, host mapping, `/api/v1/app-config`).
- depends on: A, B, `P3`.
- blocks: D (release selection), H (branding/config correctness).
4. Epic C: Workspace CRUD + membership + invites.
- depends on: A, B.
- blocks: D, E, G, H.
5. Epic D: Provisioning jobs + idempotency + runtime status APIs.
- depends on: A, B, C, I, `P1`, `P2`.
- blocks: E, H, J.
6. Epic E: Workspace runtime proxy + route ownership table implementation.
- depends on: B, C, D, `P2`.
- blocks: F, G, H, J.
7. Epic F: Share links.
- depends on: A, B, E.
- blocks: H (if share-link UI surfaces ship in V0).
8. Epic G: MCP/agent session endpoints.
- depends on: B, C, E.
- blocks: H (if agent UI surfaces ship in V0).
9. Epic H: Frontend onboarding/workspace switch/settings integration.
- depends on: B, C, D, E, I, and V0-shipped UI dependencies (F/G if included).
10. Epic J: Operational guardrails (checksum failure handling, stale-job cleanup, secret rotation runbook).
- depends on: D, E, I, `P4`.
- blocks: production rollout sign-off.

### 19.3 Decomposition Rule
1. No task decomposition may start for an epic whose dependency set (including `P*` prerequisites) is not marked complete.
2. Every decomposed task must map back to at least one criterion in section 18 and one test item in section 20.

## 20. Test Strategy by Epic
1. Epic A (schema/migrations)
- unit: migration SQL applies on empty DB.
- integration: migration re-run is idempotent.
- integration: RLS policies deny cross-workspace reads/writes for non-members.
2. Epic B (auth/session)
- unit: token verify success/failure paths.
- integration: login callback creates session cookie with required flags.
- e2e: unauthenticated -> login -> `/api/v1/me`.
3. Epic C (workspaces/invites)
- unit: invite dedupe and auto-accept logic.
- integration: create/list/membership lifecycle.
- e2e: invite flow from admin to invited user.
4. Epic D (provisioning)
- unit: state transitions and timeout/error mapping.
- unit: sandbox naming formatter/normalizer computes `sbx-{app_id}-{workspace_id}-{env}` deterministically.
- integration: idempotency key dedupe and single-active-job enforcement under concurrent requests.
- integration: create/runtime/retry responses return consistent `sandbox_name` for a workspace.
- e2e: create workspace -> provisioning -> ready/error+retry.
5. Epic E (proxy/routing)
- unit: workspace context precedence parser and conflict detection.
- integration: route ownership table behavior and `400 workspace_context_mismatch`.
- integration: request-id propagation and header-spoof rejection on private runtime auth.
- e2e: `/w/{workspace_id}` routes reach runtime and keep `X-Request-ID`.
6. Epic F (share links)
- unit: path normalization and exact-scope matcher.
- integration: revoke/expire behavior and token-hash-only persistence checks.
- e2e: auth-required share read/write happy and denied paths.
7. Epic G (MCP/agent sessions)
- unit: session ID validation and membership gate.
- integration: stream connect/input/stop lifecycle and duplicate stop idempotency.
- e2e: member can run session, non-member gets `403`.
8. Epic H (frontend UX)
- unit: state transitions for onboarding/provisioning/switch.
- integration: API client handles 401/403/409/410/503 surfaces.
- e2e: first-time onboarding and workspace switch end-to-end.
9. Epic I (app identity/config)
- unit: host->app_id resolver and mismatch detection.
- integration: `/api/v1/app-config` returns expected branding and `default_release_id`.
- e2e: app host loads expected login branding.
10. Epic J (operational guardrails)
- unit: checksum validator and error mapping (`ARTIFACT_CHECKSUM_MISMATCH`).
- integration: stale-job detector transitions timed-out `provisioning` jobs to `error`.
- integration: secret-rotation smoke test confirms runtime auth recovery.
- e2e: broken artifact fails with actionable error, fixed artifact retry succeeds.

### 20.1 Cross-Cutting Test Gaps Closed in V0
1. Contract tests: schema snapshots for critical API responses in section 11.1 (`/workspaces`, `/runtime`, `/app-config`, share endpoints).
2. Security tests: workspace boundary negative cases, path traversal attempts, forged workspace/header context, and share token leakage checks.
3. Resilience tests: injected Modal/Sprite/Supabase outage scenarios with expected user-visible failures and retries.
4. Load tests: burst create/retry on same workspace and multi-workspace concurrent provisioning to validate lock/idempotency behavior.
5. Observability tests: request-id and audit-event correlation from API ingress through runtime/provision job logs.

### 20.2 Test Exit Gate (must pass before decomposition sign-off)
1. Each acceptance criterion in section 18 has at least one mapped automated test (unit/integration/e2e).
2. CI pass for all epic suites plus cross-cutting suites in 20.1.
3. No unresolved severity-1 or severity-2 tenant-boundary/security findings.
4. Demo environment smoke tests complete with saved request IDs for traceability.

## 21. Deployment and Demo Validation per Epic (boring-ui demo app, app_id-aware)
Every epic must include:
1. deployment step via associated CLI(s)
2. demo verification in a real `boring-ui` workspace
3. captured `X-Request-ID` from at least one successful and one denied/error path

### 21.1 Epic A (schema/migrations)
CLI:
```bash
supabase db push
```
Demo validation:
1. create demo workspace in `boring-ui`.
2. confirm tables/columns/indexes exist (`workspace_provision_jobs.idempotency_key`, `workspace_runtime.release_id`, share/audit indexes).

### 21.2 Epic B (auth/session)
CLI:
```bash
modal deploy src/control_plane/modal/modal_app.py
```
Demo validation:
1. login via demo app.
2. verify `GET /api/v1/me` returns authenticated user.
3. verify invalid token path returns `401`.

### 21.3 Epic C (workspaces/invites)
CLI:
```bash
modal deploy src/control_plane/modal/modal_app.py
supabase db push
```
Demo validation:
1. create workspace from demo app.
2. invite second email and verify auto-accept on login.
3. verify duplicate invite returns `409`.

### 21.4 Epic D (provisioning)
CLI:
```bash
modal deploy src/control_plane/modal/modal_app.py
sprite status
```
Demo validation:
1. create workspace and confirm runtime transitions to `ready`.
2. trigger retry with same `idempotency_key` and verify dedupe behavior.
3. force failure case and verify UI/API show retry + explicit error code.
4. verify runtime/API-reported `sandbox_name` matches `sbx-{app_id}-{workspace_id}-{env}` and Sprite runtime identity.

### 21.5 Epic E (proxy/routing)
CLI:
```bash
modal deploy src/control_plane/modal/modal_app.py
sprite status
```
Demo validation:
1. open `/w/{workspace_id}/app` and load files/git/pty routes.
2. verify workspace mismatch returns `400 workspace_context_mismatch`.
3. verify `X-Request-ID` is visible in control-plane and runtime logs.

### 21.6 Epic F (share links)
CLI:
```bash
modal deploy src/control_plane/modal/modal_app.py
supabase db push
```
Demo validation:
1. create share link from demo app.
2. access exact path succeeds, non-matching/traversal path fails.
3. revoke/expire and verify `404`/`410` behavior.

### 21.7 Epic G (MCP/agent sessions)
CLI:
```bash
modal deploy src/control_plane/modal/modal_app.py
sprite status
```
Demo validation:
1. start agent session in demo workspace.
2. send input and receive stream events.
3. stop session and confirm clean termination.

### 21.8 Epic H (frontend UX)
CLI:
```bash
src/app/scripts/build_release_bundle.sh --release-id demo
modal deploy src/control_plane/modal/modal_app.py
```
Demo validation:
1. complete onboarding flow end-to-end in demo app.
2. switch workspace via UI and confirm hard navigation works.
3. validate settings/workspaces pages load correctly for authenticated user.

### 21.9 Epic I (app identity/config)
CLI:
```bash
modal deploy src/control_plane/modal/modal_app.py
supabase db push
```
Demo validation:
1. request `GET /api/v1/app-config` on boring-ui host and verify `app_id/name/logo/default_release_id`.
2. verify host/app mismatch returns `400 app_context_mismatch`.

### 21.10 Epic J (operational guardrails)
CLI:
```bash
modal deploy src/control_plane/modal/modal_app.py
sprite status
```
Demo validation:
1. upload intentionally bad checksum for a demo release and verify provisioning fails with `ARTIFACT_CHECKSUM_MISMATCH`.
2. verify stale provisioning job is auto-transitioned to `error` and visible in runtime status API.
3. rotate Sprite bearer and verify restored runtime proxy health after restart.

### 21.11 Cross-Epic Operational Drill (required)
1. Simulate one upstream outage (`Supabase` or `Sprite`) and verify user-facing error mapping plus alert firing.
2. Recover service, execute explicit retry flow, and verify end-to-end success with linked request IDs.
3. Record runbook execution notes before decomposition approval.

## 22. Decomposition Gate Checklist (must be true before task split)
1. Dependency gate: section 19 prerequisites and upstream epic dependencies are complete for target epic.
2. Acceptance gate: relevant section 18 criteria are explicit, status-code-defined, and observable.
3. Test gate: mapped automated tests exist per section 20 and pass in CI.
4. Operations gate: runbook, alerts, and operational drill evidence exist per sections 17 and 21.11.
5. If any gate fails, decomposition is blocked and plan must be patched first.

## 23. Post-V0 Evolution (Deferred)
1. Move from shared workspace folder to `session_worktree` isolation.
2. Later add `session_jail` isolation.
3. Replace static proxy bearer with short-lived scoped service tokens.
4. Add stronger runtime-to-control-plane trust (mTLS or equivalent).
5. Add workspace-scoped MCP server registry/config and full MCP invocation auditing.
