# Boring UI - Complete Architecture and Implementation Spec

**Document status**: Canonical target architecture  
**Last updated**: 2026-02-11  
**Applies to**: `src/front/*`, `src/back/boring_ui/api/*`

## 1. Purpose

This document defines the production architecture for Boring UI with two explicit runtime modes:

1. `local` mode: single backend API, no additional control-plane service required.
2. `hosted` mode: dual backend APIs (`Hosted API` + `Sandbox API`) with strict separation between user-facing control plane and privileged execution plane.

The goal is to make filesystem, git, and command execution safe, auditable, and multi-tenant ready while keeping local development simple.

## 2. Goals and Non-Goals

### 2.1 Goals

1. Frontend never executes privileged operations directly.
2. Filesystem, git, and shell execution run only in trusted backend context.
3. Clear security boundary for hosted deployments.
4. Strong authn/authz with short-lived credentials for internal sandbox calls.
5. Backward-compatible user experience across both modes.
6. Clear implementation map for current repository.

### 2.2 Non-Goals

1. Building a full IAM product (we integrate with OIDC providers).
2. Exposing sandbox internals directly to browsers in hosted mode.
3. Supporting arbitrary unrestricted shell execution in production.

## 3. Runtime Modes

### 3.1 Mode A: Local (Single API)

Use this for local development, single-user environments, and trusted internal use.

- Frontend calls one backend (`boring-ui API`).
- Backend directly performs file/git/exec operations in configured workspace.
- User auth can be optional or lightweight.
- No extra hosted control plane required.

### Flow

```text
Browser -> Local Boring API -> FileService/GitService/ExecService -> Workspace
```

### 3.2 Mode B: Hosted (Dual API)

Use this for production, multi-user, and internet-facing deployments.

- Frontend calls `Hosted API` only.
- Hosted API handles user auth, authorization, policy, audit.
- Hosted API calls `Sandbox API` inside sandbox/private network.
- Sandbox API performs privileged operations only after internal token validation.

### Flow

```text
Browser -> Hosted API (authz + policy) -> Sandbox API (private) -> Workspace
```

### 3.3 Mode Selection

Introduce runtime setting:

- `BORING_UI_RUN_MODE=local|hosted`

Behavior:

1. `local`: mount privileged routers directly in `create_app`.
2. `hosted`: public API exposes safe control-plane endpoints; privileged handlers call internal sandbox client.

## 4. High-Level Architecture

```text
┌───────────────────────────────────────────────────────────────────┐
│                            Frontend                               │
│                    React + Vite + DockView                       │
│   FileTree / Editor / Terminal / Chat panels                     │
└───────────────────────────────┬───────────────────────────────────┘
                                │ HTTPS (User JWT)
                                ▼
┌───────────────────────────────────────────────────────────────────┐
│                         Hosted API (Public)                       │
│ FastAPI control plane                                              │
│ - Auth middleware (OIDC JWT)                                       │
│ - Workspace authz + RBAC/ABAC                                      │
│ - Policy + rate limits + audit                                     │
│ - Proxies privileged calls in hosted mode                          │
└───────────────────────────────┬───────────────────────────────────┘
                                │ Private network (service auth)
                                ▼
┌───────────────────────────────────────────────────────────────────┐
│                      Sandbox API (Private Only)                    │
│ FastAPI/Service in sandbox                                          │
│ - File operations                                                    │
│ - Git operations                                                     │
│ - Command execution                                                  │
│ - Path jail + command policy + resource limits                      │
└───────────────────────────────┬───────────────────────────────────┘
                                ▼
                          Workspace Filesystem
```

## 5. Component Responsibilities

### 5.1 Frontend (`src/front/*`)

Responsibilities:

1. Render UI and collect user actions.
2. Attach user access token on requests to Hosted API.
3. Never store internal sandbox secrets.
4. Use capability metadata for feature gating.

Rules:

1. Hosted mode: frontend must not call sandbox URLs directly.
2. Local mode: frontend calls local API only.

### 5.2 Hosted API (`src/back/boring_ui/api/*` in hosted mode)

Responsibilities:

1. Validate user identity.
2. Authorize per workspace and operation.
3. Enforce policy (branch restrictions, command policy, quota, rate limits).
4. Emit audit records.
5. Forward approved requests to sandbox with internal capability token.

### 5.3 Sandbox API (new service module)

Responsibilities:

1. Accept only internal service-authenticated calls.
2. Validate short-lived capability token claims.
3. Execute file/git/exec operations.
4. Enforce local sandbox restrictions regardless of upstream checks.

### 5.4 Shared Storage and Workspace

1. All paths are relative to `workspace_root`.
2. Absolute paths and traversal attempts are rejected.
3. Symlink resolution must remain under workspace root.

## 6. Security Model

### 6.1 Token Types

1. **User Access Token (JWT, OIDC)**
- Issued by IdP (Auth0/Clerk/Keycloak/etc).
- Sent by browser to Hosted API.
- Contains `sub`, `org_id`, roles/scopes.

2. **Internal Capability Token (JWT, short TTL)**
- Issued by Hosted API.
- Audience: `sandbox-api`.
- Contains exact allowed operation and workspace.
- TTL: 60-300 seconds.

3. **Service Identity Credential**
- mTLS cert or signed service token between Hosted API and Sandbox API.
- Prevents direct external calls to sandbox.

### 6.2 Auth Middleware Stack (Hosted API)

Order is mandatory:

1. `RequestIdMiddleware`
2. `AuthMiddleware` (JWT verification)
3. `WorkspaceAccessMiddleware`
4. `PermissionMiddleware`
5. Route handler

### Auth middleware behavior

1. Parse `Authorization: Bearer <token>`.
2. Verify signature using JWKS.
3. Validate `iss`, `aud`, `exp`, optional `nbf`.
4. Extract claims into request context.
5. Return `401` for invalid/missing token.

### Authorization middleware behavior

1. Resolve target workspace from route/path/body.
2. Verify user membership for workspace.
3. Verify operation permission.
4. Return `403` for denied access.

### 6.3 Permission Model

Minimum permissions:

1. `files:read`
2. `files:write`
3. `git:read`
4. `git:write`
5. `exec:run`
6. `chat:use`
7. `admin:workspace`

Example role mapping:

| Role | files:read | files:write | git:read | git:write | exec:run | admin:workspace |
|------|------------|-------------|----------|-----------|----------|-----------------|
| viewer | yes | no | yes | no | no | no |
| editor | yes | yes | yes | yes | limited | no |
| admin | yes | yes | yes | yes | yes | yes |

### 6.4 Internal Capability Token Claims

Required claims:

1. `iss`: hosted API service name.
2. `aud`: `sandbox-api`.
3. `sub`: user id.
4. `workspace_id`.
5. `ops`: allowed operations list.
6. `iat`, `exp`.
7. `jti` for replay tracking.

Optional claims:

1. `path_prefixes`.
2. `git_branches`.
3. `exec_profile`.

### 6.5 Sandbox Defensive Controls

Sandbox API must independently enforce:

1. Path jail and symlink-safe validation.
2. Command allowlist.
3. CPU/memory/process/timeout limits.
4. Network egress policy (deny by default).
5. Secret isolation from workspace.

## 7. API Contracts

This section defines canonical contracts. Existing routes stay supported during migration.

### 7.1 Public Hosted API (canonical)

Base prefix: `/api/v1`

### Capabilities

- `GET /api/v1/capabilities`

Response:

```json
{
  "mode": "local",
  "features": {
    "files": true,
    "git": true,
    "exec": true,
    "chat": true
  },
  "transport": {
    "direct_sandbox": false
  }
}
```

### File operations

- `GET /api/v1/files/tree?path=.`
- `GET /api/v1/files/content?path=...`
- `PUT /api/v1/files/content?path=...`
- `DELETE /api/v1/files/content?path=...`
- `POST /api/v1/files/rename`
- `POST /api/v1/files/move`
- `GET /api/v1/files/search?q=...&path=...`

### Git operations

- `GET /api/v1/git/status`
- `GET /api/v1/git/diff?path=...`
- `GET /api/v1/git/show?path=...`
- `POST /api/v1/git/stage`
- `POST /api/v1/git/commit`
- `POST /api/v1/git/push`
- `GET /api/v1/git/log`

### Execution

- `POST /api/v1/exec/run`
- `POST /api/v1/exec/pty/start`
- `POST /api/v1/exec/pty/input`
- `POST /api/v1/exec/pty/resize`
- `POST /api/v1/exec/pty/stop`

### Chat/session helpers

- `GET /api/v1/sessions`
- `POST /api/v1/sessions`

### 7.2 Internal Sandbox API (private)

Base prefix: `/internal/v1`

Auth requirements:

1. Valid service identity.
2. Valid internal capability token.

Endpoints mirror privileged operations for proxy simplicity:

- `/internal/v1/files/*`
- `/internal/v1/git/*`
- `/internal/v1/exec/*`

Hosted API forwards normalized payloads; sandbox API returns normalized responses.

### 7.3 Backward Compatibility with Current Routes

Current routes remain available while frontend migrates:

1. `/api/tree`, `/api/file`, `/api/search`
2. `/api/git/status`, `/api/git/diff`, `/api/git/show`
3. `/ws/pty`, stream websocket routes
4. `/api/capabilities`

Compatibility policy:

1. Keep for at least one major release.
2. Add deprecation warnings in response headers.
3. Remove only after frontend cutover.

## 8. Detailed Request Flows

### 8.1 Local Mode File Write

1. Frontend `PUT /api/v1/files/content`.
2. Local API validates path and permission.
3. File service writes within workspace.
4. API returns `{ok: true, path: ...}`.

### 8.2 Hosted Mode File Write

1. Frontend sends user JWT to Hosted API.
2. Hosted auth middleware validates JWT.
3. Hosted authz checks `files:write` on workspace.
4. Hosted API mints capability token (`ops=[files:write]`, short TTL).
5. Hosted API calls sandbox `/internal/v1/files/content`.
6. Sandbox validates service identity + capability token.
7. Sandbox validates path jail and writes file.
8. Sandbox returns result; Hosted returns response to frontend.
9. Hosted writes audit event.

### 8.3 Hosted Mode Git Push

1. Hosted authz verifies `git:write` and branch policy.
2. Hosted obtains git credentials from secret store (never from frontend).
3. Hosted issues capability with `ops=[git:push]` and branch constraints.
4. Sandbox executes push with controlled environment.
5. Hosted logs actor, branch, commit sha, outcome.

## 9. Implementation Plan in This Repository

### 9.1 New/Updated Modules

1. `src/back/boring_ui/api/config.py`
- Add `run_mode` and security settings.

2. `src/back/boring_ui/api/app.py`
- Branch behavior by `run_mode`.
- Mount mode-specific routers.

3. `src/back/boring_ui/api/security/` (new)
- `jwt_verifier.py`
- `auth_context.py`
- `middleware.py`
- `permissions.py`
- `capability_tokens.py`

4. `src/back/boring_ui/api/modules/sandbox_proxy/` (new)
- Hosted->sandbox HTTP client.

5. `src/back/boring_ui/api/modules/internal/` (new or separate service package)
- Internal file/git/exec handlers.

6. `src/front/hooks/*`
- Ensure frontend always uses Hosted API in hosted mode.
- Remove direct sandbox token dependency in hosted mode.

### 9.2 `create_app` Mode Wiring

Pseudo-logic:

```python
if config.run_mode == "local":
    mount_files_git_exec_direct()
    mount_optional_chat_routes()
elif config.run_mode == "hosted":
    mount_auth_middleware()
    mount_control_plane_routes()
    mount_proxy_routes_for_files_git_exec()
else:
    raise ValueError("Invalid run mode")
```

### 9.3 Auth Context Shape

```python
@dataclass
class AuthContext:
    user_id: str
    org_id: str | None
    workspace_ids: list[str]
    roles: list[str]
    scopes: list[str]
```

Attach to request state:

```python
request.state.auth = AuthContext(...)
```

### 9.4 Capability Token Issuance

```python
payload = {
  "iss": "boring-ui-hosted",
  "aud": "sandbox-api",
  "sub": auth.user_id,
  "workspace_id": workspace_id,
  "ops": ["files:write"],
  "iat": now,
  "exp": now + 120,
  "jti": str(uuid4()),
}
```

### 9.5 Sandbox Validation

Sandbox request is authorized only if all checks pass:

1. Service identity valid.
2. Capability token signature valid.
3. `aud` = sandbox.
4. Token not expired.
5. Required operation included in `ops`.
6. Workspace and path constraints satisfied.

## 10. Filesystem, Git, and Exec Safety Requirements

### 10.1 Filesystem

1. Normalize and resolve every incoming path.
2. Reject if resolved path is outside workspace root.
3. For write operations, optional file extension/path policy.
4. Log all write/delete/rename actions.

### 10.2 Git

1. Execute git with explicit `cwd=workspace_root`.
2. Use arg arrays only; never shell interpolation.
3. Restrict high-risk operations unless admin (for example `reset --hard`).
4. Apply protected-branch policy server-side.
5. Keep credentials in backend secret store only.

### 10.3 Exec

1. Support allowlisted commands per role/profile.
2. Enforce max runtime, max output bytes, process limits.
3. Sanitize environment variables passed to child processes.
4. Disable outbound network unless explicitly allowed.

## 11. Chat/Agent Integration

Chat remains optional and separate from privileged filesystem/git operations.

Rules:

1. Local mode may still use direct local chat service where acceptable.
2. Hosted mode must not expose sandbox internal secrets to browser.
3. If websocket auth is needed in browser, use short-lived query token or secure cookie, not custom WS headers in browser constructor.

## 12. Observability and Audit

### 12.1 Required Structured Log Fields

1. `ts`
2. `request_id`
3. `user_id`
4. `workspace_id`
5. `operation`
6. `resource_path` (if applicable)
7. `result` (`ok`/`error`)
8. `latency_ms`

### 12.2 Audit Events

Capture at minimum:

1. File write/delete/rename/move.
2. Git commit/push/branch operations.
3. Exec command invocations.
4. Authorization denials.

### 12.3 Metrics

1. Request counts by route/status.
2. Auth failures and permission denials.
3. Sandbox operation latency.
4. Active PTY/exec sessions.

## 13. Configuration

### 13.1 Local Mode Example

```bash
export BORING_UI_RUN_MODE=local
export WORKSPACE_ROOT=/home/ubuntu/projects/boring-ui
export CORS_ORIGINS=http://localhost:5173
```

### 13.2 Hosted API Example

```bash
export BORING_UI_RUN_MODE=hosted
export OIDC_ISSUER=https://issuer.example.com/
export OIDC_AUDIENCE=boring-ui-api
export SANDBOX_INTERNAL_BASE_URL=http://sandbox-api:9000
export SANDBOX_SERVICE_SIGNING_KEY=<secret>
```

### 13.3 Sandbox API Example

```bash
export SANDBOX_API_BIND=0.0.0.0:9000
export SANDBOX_WORKSPACE_ROOT=/workspace
export SANDBOX_EXPECTED_AUDIENCE=sandbox-api
export SANDBOX_SERVICE_SIGNING_KEY=<same-shared-or-public-key>
```

## 14. Error Model

Use stable error object:

```json
{
  "error": {
    "code": "forbidden",
    "message": "Missing permission git:write",
    "request_id": "..."
  }
}
```

HTTP mapping:

1. `400` invalid request/path.
2. `401` auth failure.
3. `403` permission denied.
4. `404` resource not found.
5. `409` conflict.
6. `429` rate limit.
7. `500` internal error.

## 15. Migration Plan

### Phase 1: Foundation

1. Add run mode config.
2. Add auth context and JWT verifier.
3. Add permission checks to existing routes.

### Phase 2: Hosted Proxy Path

1. Implement sandbox internal API client.
2. Add capability token issuance/verification.
3. Route file/git/exec via proxy in hosted mode.

### Phase 3: Hardening

1. Enforce command policy and branch policy.
2. Add full audit and metrics dashboards.
3. Lock down sandbox network and service identity.

### Phase 4: Cleanup

1. Migrate frontend to `/api/v1/*` canonical endpoints.
2. Mark old endpoints deprecated.
3. Remove deprecated paths after adoption.

## 16. Testing Strategy

### 16.1 Unit

1. JWT verification edge cases.
2. Permission matrix checks.
3. Path traversal and symlink escape tests.
4. Capability token claim validation.

### 16.2 Integration

1. Local mode file/git/exec operations.
2. Hosted mode proxy flow with sandbox mock.
3. Forbidden operations and branch protection.

### 16.3 End-to-End

1. Editor save -> file write -> git status update.
2. Commit/push flow with policy checks.
3. Session lifecycle and websocket reconnect behavior.

### 16.4 Security

1. Replay token attempts.
2. Expired/invalid JWT behavior.
3. Path traversal payload corpus.
4. Command injection attempts.

## 17. Acceptance Criteria

Implementation is complete when:

1. `local` mode works without control-plane dependencies.
2. `hosted` mode requires Hosted API and blocks direct sandbox public access.
3. All privileged operations are authenticated, authorized, and audited.
4. Frontend behavior is consistent across modes.
5. Test suite covers success and denial paths.

## 18. Notes on Current State

Current codebase already includes:

1. Core file routes (`/api/tree`, `/api/file`, `/api/search`).
2. Core git routes (`/api/git/status`, `/api/git/diff`, `/api/git/show`).
3. Capabilities endpoint (`/api/capabilities`).
4. Sandbox and companion managers.

This spec supersedes ad-hoc direct token exposure patterns for hosted production and defines the required target-state architecture.
