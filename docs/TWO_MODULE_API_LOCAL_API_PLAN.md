# Two-Module Refactor Plan (`api` + `local-api`)

## 1. Goal

Ship a clean two-module backend where filesystem location is a runtime parameter, not an architecture fork.

Final runtime invariant:

- Hosted/Sprites: `frontend -> api (control plane proxy) -> local-api in sprite`
- Local: `frontend -> api`, with `local-api` mounted in-process (same Python process)
- Browser never calls sprite endpoints directly
- Browser never receives Sprites API token
- `local-api` stays private and reachable only through control-plane routes

This plan intentionally optimizes for fast delivery over backward compatibility.

Authoritative contract decision for `bd-2j57.1`:

- Canonical browser API is `/api/v1/*` for privileged workspace operations.
- Canonical private workspace API is `/internal/v1/*`.
- No runtime compatibility wrappers for legacy privileged browser routes.
- No hidden path rewrites for privileged operations.
- Control-plane and workspace-plane ownership is explicit and non-overlapping.

## 2. Non-Negotiable Design Decisions

1. Exactly two backend modules:
- `api`: control plane (user auth, sandbox management, proxy, policy, service orchestration)
- `local-api`: workspace plane (file/git/exec on one workspace root)

2. `local-api` auth model:
- No end-user auth in `local-api`
- Trust boundary is enforced by deployment topology: `local-api` is private
- For Sprites, private reachability is through Sprites proxy transport, not browser traffic

3. Transport model in Sprites mode:
- Control plane connects directly to Sprites Proxy API from backend
- No `sprite proxy` CLI tunnel in production runtime path

4. Fast-path scope:
- Single hardcoded sprite target for now
- DB-backed workspace->sprite mapping comes later

5. Hard cut:
- Remove old `internal_app`/`internal_api` ownership paths after rewire
- No compatibility wrappers

## 3. Target Module Ownership

## 3.1 `api` (Control Plane)

Location: `src/back/boring_ui/api/`

Responsibilities:

- User authentication and permission checks
- Workspace/session authorization
- Sandbox provider lifecycle management
- Routing/proxy from frontend routes to workspace plane
- Sprites transport client
- Capability issuance and validation (control-plane side)
- Request context, trace IDs, structured errors, logging

Key files (target ownership):

- `app.py`
- `auth.py` (reuse: `ServiceTokenIssuer` and `OIDCVerifier` from REUSE_INVENTORY.md)
- `auth_middleware.py` (reuse: `add_oidc_auth_middleware`, `AuthContext`, `require_permission` from REUSE_INVENTORY.md)
- `service_auth.py`, `sandbox_auth.py`
- `config.py` (reuse: `RunMode`, `APIConfig` from REUSE_INVENTORY.md)
- `capabilities.py`, `capability_tokens.py`
- `logging_middleware.py` (reuse: `add_logging_middleware`, `get_request_id`, `propagate_request_context` from REUSE_INVENTORY.md)
- `app_mode_composition.py`
- `error_codes.py` (new)
- `modules/sandbox/manager.py`, `provider.py`, `providers/*`
- `modules/sandbox/hosted_client.py` (refactor to transport interface)

**Reuse Constraints** (see `.planning/bd-1adh/REUSE_INVENTORY.md`):
- ✅ ServiceTokenIssuer: direct import, no modifications
- ✅ OIDCVerifier: direct import for hosted JWT verification
- ✅ AuthMiddleware: extend permissions if needed, preserve error semantics
- ✅ RunMode/APIConfig: direct import, extend fields only if needed
- ✅ LoggingMiddleware: import and use for trace propagation

## 3.2 `local-api` (Workspace Plane)

Location: `src/back/boring_ui/api/local_api/`

Responsibilities:

- Workspace-scoped file endpoints
- Workspace-scoped git endpoints
- Workspace-scoped exec endpoints
- Internal health and info endpoints

Key files:

- `app.py` (`create_local_api_app`)
- `router.py` (`create_local_api_router`)
- `files.py`
- `git.py`
- `exec.py`

Policy:

- Reuse shared policy from `src/back/boring_ui/api/modules/sandbox/policy.py`
- Do not create duplicate policy logic inside `local_api`

## 4. Runtime Modes and Network Topology

## 4.1 Local Mode

- Control plane and local-api run in-process
- Frontend talks only to `api`
- No network hop between control plane and local-api
- Workspace root is host-local path

## 4.2 Hosted + Sprites Mode

- Control plane runs outside sprite
- local-api runs inside sprite, bound to localhost in the sprite VM
- Control plane reaches local-api via Sprites proxy WebSocket transport
- Workspace root is sprite filesystem path

Important clarification:

- `INTERNAL_SANDBOX_URL` is only relevant for non-Sprites hosted providers
- In Sprites mode, control plane does not use `INTERNAL_SANDBOX_URL`
- In Sprites mode, target is `{sprite_name, local_api_port}` and connection is through Sprites proxy API

## 4.3 Port Binding Rules by Topology

| Topology | local-api bind host | local-api port | Reachability |
|---|---|---|---|
| local in-process | no separate listener | n/a | mounted router only |
| local standalone dev | `127.0.0.1` | `BORING_UI_LOCAL_API_PORT` | host-local only |
| hosted non-sprites | `0.0.0.0` | `BORING_UI_LOCAL_API_PORT` | private network from control plane |
| hosted + sprites | `127.0.0.1` (inside sprite) | `SPRITES_LOCAL_API_PORT` | via Sprites proxy transport only |

Startup requirement:

- Log effective runtime bind decision on boot (`mode`, `provider`, `host`, `port`) for both control-plane and local-api processes.

## 5. Public and Internal API Contracts

## 5.1 Browser-Facing Canonical Contract

Control-plane endpoints exposed to browser clients:

- `/api/capabilities`
- `/api/config`
- `/api/project`
- `/api/sessions`
- `/api/v1/files/list`
- `/api/v1/files/read`
- `/api/v1/files/write`
- `/api/v1/git/status`
- `/api/v1/git/diff`
- `/api/v1/git/show`
- `/api/v1/exec/run`
- `/ws/pty/{session_id}` (when PTY router enabled)
- `/ws/stream/{session_id}` (when chat router enabled)
- `/health`

Explicit non-goals (not browser-facing contract):

- No `/api/tree` or `/api/file` privileged compatibility routes.
- No legacy privileged `/api/git/*` compatibility surface.
- No browser access to `/internal/*`.
- No runtime alias layers for privileged operations.

## 5.2 Internal `local-api` Contract

Internal-only workspace plane endpoints:

- `/internal/info`
- `/internal/v1/files/*`
- `/internal/v1/git/*`
- `/internal/v1/exec/*`

`local-api` is internal-only and not exposed to browser.

Ownership map:

- `api/app.py`: mode-aware composition and trust boundaries.
- `api/v1_router.py`: canonical browser-facing privileged contract.
- `api/local_api/router.py`: canonical internal workspace contract.
- `api/transport.py` + `api/hosted_client.py`: control-plane to workspace transport.

**Authentication model** (reuse from REUSE_INVENTORY.md):
- In LOCAL mode: no authentication (internal routers in-process)
- In HOSTED mode: control-plane reaches local-api via private transport (Sprites proxy or internal URL), no browser auth needed
- local-api does NOT implement end-user auth; trust boundary is deployment topology
- Control-plane propagates `X-Request-ID` and internal metadata headers for trace correlation (use `propagate_request_context` helper)

## 5.3 Sprites Transport Contract (Precise)

Reference:

- `https://sprites.dev/api/sprites/proxy`

Control-plane transport steps:

1. Open WebSocket:
- `wss://api.sprites.dev/v1/sprites/{sprite-name}/proxy`

2. Add backend-only auth header:
- `Authorization: Bearer ${SPRITES_TOKEN}`

3. Send handshake frame:
- `{"host":"localhost","port":<SPRITES_LOCAL_API_PORT>}`

4. On connected response, relay raw TCP bytes:
- Write raw HTTP/1.1 request bytes for `/internal/*`
- Parse raw HTTP response bytes into status, headers, body
- v1 simplification: one HTTP request per WebSocket connection
- Control-plane request must set `Connection: close`
- local-api response for `/internal/v1/*` must be non-streaming with `Content-Length` (no chunked transfer in v1)

5. Timeouts and parser safety limits:
- `connect_timeout_sec`: default `5`
- `handshake_timeout_sec`: default `5`
- `response_timeout_sec`: default `30` (or route-specific override)
- `max_response_bytes`: default `10MB`
- Missing `Content-Length`, malformed status line, or byte count overflow -> map to `502` with `local_api_protocol_error`

6. Error mapping:
- Handshake timeout/invalid response -> `502`
- Relay timeout -> `504`
- Parsed internal HTTP status -> preserve status/body

7. Retry defaults:
- Retryable: connect reset/timeout/`502`/`503`/`504`
- Non-retryable: `400`/`401`/`403`/`404`/`422`
- Default max attempts: `3`
- Backoff: `100ms`, `300ms`, `900ms` (configurable)

## 6. Configuration Interface (Actual Parameter Surface)

The controlling parameter is runtime config loaded by `api`.

## 6.1 Canonical Config Object

Reuse existing `RunMode` and `APIConfig` from `src/back/boring_ui/api/config.py` (see REUSE_INVENTORY.md).

**RunMode enum** (existing, MUST reuse):
- `LOCAL`: Single backend with direct operations
- `HOSTED`: Dual API model with control plane (public) and data plane (private)

**APIConfig dataclass** (existing, MUST reuse):
- `workspace_root`: Path to workspace filesystem
- `run_mode`: RunMode.LOCAL or RunMode.HOSTED
- `cors_origins`: CORS allow-list
- `filesystem_source`: 'local', 'sandbox', or 'sprites'
- `pty_providers`: Shell command config
- `oidc_issuer`, `oidc_audience`, `oidc_cache_ttl_seconds`: OIDC JWT config

**Extended config fields** (add to APIConfig if needed):
- `sandbox_provider`: 'local' | 'sprites' | ...
- `local_api_port`: default `8001`
- `control_plane_port`: default `8000`
- `sprites_token`: backend secret
- `sprites_target_sprite`: hardcoded target sprite for current phase
- `sprites_local_api_port`: default `8001`
- `internal_sandbox_url`: only for non-Sprites hosted providers
- `transport_timeout_sec`
- `transport_max_retries`
- `trace_id_header`: default `X-Trace-ID`

**Validation** (use `APIConfig.validate_startup()`, existing):
- Enforces required env vars per run mode
- Raises ValueError with actionable error text on failure

## 6.2 Env Var Mapping (move-fast, explicit)

Required now (Sprites hosted path):

- `BORING_UI_RUN_MODE=hosted`
- `SANDBOX_PROVIDER=sprites`
- `SPRITES_TOKEN=<secret>`
- `SPRITES_TARGET_SPRITE=<sprite-name>`
- `SPRITES_LOCAL_API_PORT=8001`

Required now (local mode):

- `BORING_UI_RUN_MODE=local`
- `WORKSPACE_ROOT=<host-workspace-path>`

Non-Sprites hosted only:

- `INTERNAL_SANDBOX_URL=http://...`

Validation rules at startup:

- If `run_mode=hosted` and `sandbox_provider=sprites`, require `SPRITES_TOKEN`, `SPRITES_TARGET_SPRITE`, and `SPRITES_LOCAL_API_PORT`
- If `sandbox_provider!=sprites` in hosted, require `INTERNAL_SANDBOX_URL`
- Fail fast with actionable error text

Startup matrix enforcement:

- Hosted + sprites boot must fail if `BORING_UI_RUN_MODE` is missing or not `hosted`.
- Validation error must return one aggregated message listing all missing/invalid keys.

## 6.3 Target Resolution Interface (Service Discovery Seam)

Even in single-sprite move-fast mode, control-plane target lookup goes through one interface.

```python
@dataclass
class WorkspaceTarget:
    provider: str
    sprite_name: str | None
    local_api_port: int | None
    internal_base_url: str | None

class TargetResolver(ABC):
    async def resolve(self, workspace_id: str, user_id: str | None) -> WorkspaceTarget: ...
```

Current sprint implementation:

- `StaticTargetResolver` (env/hardcoded values only).
- Sprites provider returns `WorkspaceTarget(provider="sprites", sprite_name=SPRITES_TARGET_SPRITE, local_api_port=SPRITES_LOCAL_API_PORT)`.
- Non-sprites hosted returns `WorkspaceTarget(provider="<provider>", internal_base_url=INTERNAL_SANDBOX_URL)`.

Future replacement:

- `DbTargetResolver` with the same interface (`workspace/user -> provider target`), no control-plane call-site changes.

## 7. Transport Abstraction and Interfaces

Define a unified control-plane transport interface to avoid provider-specific sprawl.

```python
class WorkspaceTransport(ABC):
    async def request(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout_sec: float = 30.0,
        trace_id: str | None = None,
    ) -> WorkspaceResponse: ...

    async def health_check(self, timeout_sec: float = 5.0) -> HealthStatus: ...
```

```python
@dataclass
class WorkspaceResponse:
    status_code: int
    headers: dict[str, str]
    body: bytes
    elapsed_sec: float
    transport_type: str
```

Transport implementations:

- `HTTPInternalTransport` (`INTERNAL_SANDBOX_URL`)
- `SpritesProxyTransport` (`sprites/proxy` WebSocket relay)

## 8. Error Model and Observability

## 8.1 Structured Error Codes

Create `error_codes.py` with stable control-plane error codes:

- `sprites_handshake_timeout`
- `sprites_handshake_invalid`
- `sprites_relay_lost`
- `local_api_unavailable`
- `local_api_timeout`
- `transport_retry_exhausted`

Standard error payload:

```json
{
  "error_code": "sprites_handshake_timeout",
  "status_code": 502,
  "message": "Failed to connect to local-api in sprite",
  "trace_id": "<uuid>",
  "is_retryable": true,
  "retry_after_sec": 1
}
```

## 8.2 Request Context Propagation

Reuse existing logging middleware from `src/back/boring_ui/api/logging_middleware.py` (see REUSE_INVENTORY.md).

**Request ID generation** (existing `RequestIDMiddleware`):
- Generates unique UUID for each request
- Attaches to `request.state.request_id`
- Includes in response headers (`X-Request-ID`, `X-Process-Time`)

**Structured logging** (existing `StructuredLoggingMiddleware`):
- JSON-formatted logs with structured fields
- Captures: request_id, method, path, status, latency_ms, user_id
- Skips health checks, logs errors at WARNING/ERROR level

**Context propagation** (use `propagate_request_context()` helper):
- Builds headers for outbound requests to maintain trace correlation
- Propagates `X-Request-ID` and optional `X-User-ID`, `X-Workspace-ID`
- Control plane -> local-api: include headers in all proxied requests

**Audit logging** (use `AuditLogger` from `src/back/boring_ui/api/audit.py`):
- Log all sensitive operations (auth success/failure, file ops, exec)
- Use `request_id` from logging middleware for correlation
- Persists events to audit trail for compliance/forensics

## 9. Workspace Isolation and Auth Scope

Current-phase behavior:

- Single workspace per running local-api instance
- local-api enforces path scoping to configured workspace root
- Browser/user auth stays in control plane
- local-api does not implement independent user auth

Future-ready seam (not implemented now):

- Swap hardcoded workspace binding for DB-backed workspace resolution and RBAC in control plane

## 10. Health Contract

Adopt a consistent `/health` shape for control-plane and local-api.

Response shape:

```json
{
  "status": "ok|degraded|unhealthy",
  "service": "api|local-api",
  "checks": {
    "filesystem": "ok",
    "git": "ok",
    "transport": "ok"
  },
  "timestamp": "<iso8601>"
}
```

Health rule:

- `/health` is the canonical readiness endpoint shape.

## 11. Workstreams and Dependency Order

Execution order is intentionally serial on critical path:

1. WS-A: Build `local_api` package and move handlers
2. WS-B: Rewire control plane imports + transport abstraction + remove legacy modules
3. WS-C: Docs and deployment matrix updates
4. WS-D: Cleanup of temporary artifacts/docs noise

Parallelizable after WS-B starts:

- test expansion
- observability refinements

## 12. Detailed Workstream Tasks

## 12.1 WS-A (`local_api` package extraction)

- Create `src/back/boring_ui/api/local_api/`
- Move `internal_files.py`, `internal_git.py`, `internal_exec.py` logic into `files.py`, `git.py`, `exec.py`
- Add `router.py` composer and `app.py` factory
- Keep internal endpoint paths unchanged
- **Reuse**: Import `propagate_request_context` in `app.py` for trace correlation (see REUSE_INVENTORY.md)

## 12.2 WS-B (Control-plane rewiring)

- Replace imports of `internal_app` and `internal_api`
- Introduce `WorkspaceTransport` + implementations
- Route Sprites provider through `SpritesProxyTransport`
- Remove `src/back/boring_ui/api/internal_app.py`
- Remove `src/back/boring_ui/api/modules/sandbox/internal_api.py`
- Ensure hosted capability payload never includes direct local-api/sprite endpoint URLs
- **Execution checklist** (prevent rebuilding existing components):
  - ✅ Import `ServiceTokenIssuer`, `OIDCVerifier` from `auth.py` (DO NOT create new token systems)
  - ✅ Import `add_oidc_auth_middleware`, `AuthContext`, `require_permission` from `auth_middleware.py` (DO NOT bypass auth)
  - ✅ Import `RunMode`, `APIConfig` from `config.py` (DO NOT create custom config loading)
  - ✅ Import `add_logging_middleware`, `get_request_id`, `propagate_request_context` from `logging_middleware.py` (DO NOT skip trace correlation)
  - ✅ Import `audit_logger` from `audit.py` (DO NOT rebuild audit trail)
  - ✅ Verify no duplicate code for auth/config/logging/audit (see `.planning/bd-1adh/REUSE_INVENTORY.md` for full anti-patterns)

## 12.3 WS-C (Docs and deployment matrix)

Update docs with explicit ownership and mode behavior:

- `docs/DEPLOYMENT_MATRIX.md`
- `docs/TWO_MODULE_API_LOCAL_API_PLAN.md` (this file)

Must include:

- Local vs Hosted/Sprites data flow
- Env var matrix
- Security rule: no direct browser->sprite/local-api
- Sprites transport contract with doc link

## 12.4 WS-D (cleanup)

- Remove stale one-off probe artifacts not referenced by docs
- Keep proof artifacts that are required by test report strategy
- Update `.gitignore` if needed

## 13. Test Strategy (Expanded)

## 13.1 Automated Contract Tests

Add transport-level tests:

- Sprites handshake success
- Sprites handshake timeout -> `502`
- Relay timeout -> `504`
- HTTP parse correctness for proxied responses
- Retry/backoff behavior

Add integration tests:

- control-plane routes still resolve correctly in local and hosted modes
- local-api private boundary (no browser direct URL leakage)
- auth middleware + capability behavior unchanged for frontend-facing flows

## 13.2 Required Live Sprites Validation (Your org’s existing sprite)

Run app against the single current sprite and verify:

1. File tree source correctness:
- UI shows sprite filesystem, not host-local filesystem

2. Bidirectional file operations:
- UI create/edit/delete reflected in sprite shell
- sprite shell edits reflected in UI after refresh/reload

3. Git parity:
- UI git status matches `sprite exec git status`

4. Agent chat path:
- Send chat message and receive response through control-plane routed path

5. Boundary:
- No direct browser calls to sprite/local-api endpoints
- Browser network capture must show:
  - zero requests to `api.sprites.dev`
  - zero requests to `*.sprites.app`
  - zero requests to `/internal/*`

## 13.3 Proof Report Requirement (Showboat + Rodney)

Use:

- `uvx showboat`
- `uvx rodney`

Produce report with:

- command transcript (including sprite selection and startup commands)
- screenshot evidence (file tree, file operations, chat response)
- cross-verification snippets from `sprite exec`
- pass/fail table per required behavior
- one network evidence artifact (HAR/export/log) proving no direct browser calls to sprite/local-api
- explicit grep/assert output showing zero matches for `api.sprites.dev`, `\\.sprites\\.app`, and `/internal/`

Recommended artifact:

- `docs/HOSTED_UI_SHOWBOAT_RODNEY_PROOF.md`

## 14. Deployment Matrix (Condensed)

| Mode | Filesystem location | Control-plane -> local-api path | Browser direct sandbox access |
|---|---|---|---|
| local | host local FS | in-process router mount | no |
| hosted + sprites | sprite FS | Sprites Proxy WebSocket transport | no |
| hosted non-sprites | provider FS | HTTP via `INTERNAL_SANDBOX_URL` | no |

## 15. Accepted / Partial / Deferred Revisions from External Review

## 15.1 Fully Accepted Now

- Transport interface and retry contract
- Structured error codes and trace propagation
- Explicit port/bind strategy by mode
- Standard health contract
- Expanded transport/integration/live test coverage
- Config schema with startup validation
- Documentation clarity and workstream ordering (`WS-A -> WS-B -> WS-C/WS-D`)

## 15.2 Partially Accepted (Scope-limited this sprint)

- Service discovery: interface seam kept, implementation remains hardcoded single-sprite for now
- Workspace isolation/RBAC: enforce workspace scoping now; full RBAC model deferred
- Capability tokens: keep current control-plane auth model and tighten docs; full token lifecycle hardening can follow
- OpenAPI and sequence diagrams: update core docs now, full generated-contract pipeline later

## 15.3 Deferred (explicitly not in this sprint)

- Multi-sprite routing and load balancing
- Full graceful-degradation operation queue/fallback orchestration
- Full runbook suite and large doc tree reorganization

## 16. Risks and Mitigations

1. Transport edge-case bugs in raw TCP relay
- Mitigation: strict handshake validation, parser tests, timeout tests, trace IDs

2. Import breakages from hard cut
- Mitigation: remove legacy modules only after all call sites are updated in same PR stack

3. Misconfigured sprite target
- Mitigation: startup config validation + explicit health checks + live smoke script

4. Security regression (URL leakage)
- Mitigation: capability payload tests and manual browser-network verification

## 17. Acceptance Criteria

Refactor is accepted when all are true:

1. Two-module ownership is real in code (`api` + `local_api`), legacy internal module entry points removed.
2. Sprites hosted path works through backend direct Sprites proxy transport.
3. Browser does not call sprite/local-api directly and never sees Sprites token.
4. Local and hosted test suites pass, including transport contract tests.
5. Live single-sprite validation passes for filesystem, git, and chat.
6. Showboat/Rodney proof report is produced and committed.
7. Browser network assertions pass with zero direct calls to Sprites API/domain/internal local-api paths.
8. **Reuse verification** (bd-1adh.1.2): All auth/config/audit/logging components reused from existing modules (no duplicate implementations)
   - ✅ ServiceTokenIssuer used from `auth.py`
   - ✅ OIDCVerifier used from `auth.py`
   - ✅ AuthMiddleware used from `auth_middleware.py`
   - ✅ RunMode/APIConfig used from `config.py`
   - ✅ LoggingMiddleware used from `logging_middleware.py`
   - ✅ AuditLogger used from `audit.py`
   - See `.planning/bd-1adh/REUSE_INVENTORY.md` for full component inventory and reuse constraints

## 18. Component Reuse Reference

**CRITICAL: Refer to `.planning/bd-1adh/REUSE_INVENTORY.md` before implementing any of the following:**
- Authentication (ServiceTokenIssuer, OIDCVerifier, AuthMiddleware)
- Configuration (RunMode, APIConfig)
- Logging and tracing (LoggingMiddleware, get_request_id)
- Audit and compliance (AuditLogger, AuditStore)

The reuse inventory documents:
- Module locations and import paths
- Core responsibilities and capabilities
- Integration patterns and usage examples
- Reuse constraints (MUST vs MUST NOT)
- Test coverage and existing tests
- Anti-patterns to avoid

**Purpose**: Prevent accidental reinvention and ensure consistent patterns across api and local-api modules.

**Ownership**: When implementing WS-B (control-plane rewiring), reference REUSE_INVENTORY.md for each major concern to ensure reuse.

## 19. Source Links

- Sprites proxy endpoint docs: `https://sprites.dev/api/sprites/proxy`
- Sprites API index: `https://sprites.dev/api`
- Showboat/Rodney reference: `https://simonwillison.net/2026/Feb/10/showboat-and-rodney/`
- Component Reuse Inventory: `.planning/bd-1adh/REUSE_INVENTORY.md`
