# Remote Sandbox Filesystem Plan (V0)

## Goal

Ship the first working sandbox mode with minimal moving parts, while keeping browser-visible behavior unchanged.

## Assumptions (explicit for v0)

- A specific sprite is already created and reachable from the control plane.
- The workspace API service inside the sprite is already deployed and configured with a stable URL base path (for example `/internal/v1`), independent of filesystem folder layout.
- The workspace API service exposes `/healthz` and a compatibility endpoint (for example `/__meta/version`).
- Workspace service responses include an internal API version marker (header or metadata field) that control plane can validate.
- Exec sessions are long-lived enough for normal interactive usage, but may be terminated by provider policy.
- Frontend treats `session_id` as an opaque identifier.
- Control plane has a stable identity context for `user_id` and `workspace_id` token binding (authenticated identity or deterministic fallback identity in non-auth mode).
- Non-auth fallback identity mode is single-tenant only; multi-tenant deployment requires authenticated per-user identity binding.

## Deployment Layout (required)

### Repo layout (boring-ui-restart)

- Keep control-plane code under `src/back/boring_ui/api`.
- Keep workspace-service code isolated under a distinct module (for example `src/back/boring_ui/workspace_service`).
- Keep sandbox/provider integration under dedicated module boundaries (for example `src/back/boring_ui/sandbox`).
- Keep runtime/deployment assets in dedicated deployment paths (for example `deploy/sandbox/*`).

### V0 deployment mechanism (script-first)

- V0 deployment is script-based inside sandbox workflows.
- Expected flow:
  - sync/copy workspace-service source to sandbox service runtime path
  - apply env/policy files
  - start or restart workspace API via Sprites Services command
  - configure exec command profiles used by PTY/chat
  - run smoke checks (`/healthz`, version compatibility, minimal exec attach)
- V0 explicitly does **not** require wheel/artifact packaging.

### Required v0 deploy scripts (repo-side)

- `deploy/sandbox/deploy_workspace_service.sh` (idempotent source sync + config apply).
- `deploy/sandbox/restart_workspace_service.sh` (service start/restart command).
- `deploy/sandbox/configure_exec_profiles.sh` (PTY/chat exec template setup).
- `deploy/sandbox/smoke_check.sh` (health + compatibility + exec sanity checks).

### Sprite filesystem layout

- Separate user workspace from service runtime and secrets.
- Recommended structure:
  - `/home/sprite/workspace` for user/project files only.
  - `/srv/workspace-api` (or equivalent) for workspace-service code/runtime.
  - `/home/sprite/.auth` for secrets/internal auth materials (restricted permissions).
  - distinct run/log/tmp directories outside user workspace.

### Invariant for this layout

- Workspace root for file tools is the user workspace directory only (for example `/home/sprite/workspace`).
- Service code/runtime/secrets must not live under workspace root.

## Definitions and Invariants

### Definitions

- **Control plane**: this FastAPI app that owns all browser-facing HTTP and WS endpoints.
- **Workspace service**: the HTTP service in the sprite that performs filesystem/git/search/session HTTP operations.
- **Exec session**: Sprites-managed interactive session used for PTY and chat streaming in sandbox mode.
- **Parity**: browser-observed behavior (routes, shapes, semantics) is consistent between `local` and `sandbox` for in-scope features.

### Invariants

- Browser routes and message envelopes remain stable.
- Provider credentials never appear in browser payloads, query params, logs, or browser-facing error bodies.
- Path traversal protections apply in both modes (control plane and workspace service).
- No client-controlled command text is executed in sandbox mode.
- Any degraded behavior remains schema-compatible with current frontend expectations.

## Initial SLO Targets (validate and adjust)

- Workspace service readiness check completes within `<= 5s` on warm start.
- PTY/chat exec reattach succeeds `>= 99%` under transient disconnects, measured as successful reattach within `<= 10s`.
- `/api/tree` p95 latency in sandbox mode remains within an acceptable multiplier of local mode for typical repositories.
- `/ws/pty` median input-to-output latency is `<= 150ms` on warm path under normal load.

## Locked Decisions

- Runtime mode is config-only: `WORKSPACE_MODE=local|sandbox`.
- Sandbox target is fixed server-side in v0.
- Sprite and workspace service are pre-provisioned and already running.
- Browser never calls Sprites directly.
- `/ws/pty` uses Sprites Exec in sandbox mode.
- `/ws/claude-stream` uses Sprites Exec in sandbox mode.
- Chat in sandbox mode is Exec-only (no workspace-service chat websocket).
- In sandbox mode, `session_id` is a server-issued opaque token (not raw provider id).
- PTY/chat command startup is server-owned templates only:
  - templates selected from fixed allowlist
  - parameter substitution strictly validated and escaped
  - template id logged for audit/debug without secrets
- V0 deploy path is script-based (source sync + service restart); artifact/wheel packaging is deferred to V1.

## Scope

### In scope

- Keep current frontend routes unchanged.
- Add local/sandbox runtime mode switch.
- Route file/git/search/session HTTP in sandbox mode through backend relay to workspace service.
- Route PTY/chat websocket traffic in sandbox mode through backend relay to Sprites Exec.
- Keep current message shapes compatible for PTY/chat.
- Add startup validation for sandbox env config and readiness checks.

### Out of scope

- Sandbox lifecycle create/start/stop APIs.
- Per-user sandbox routing.
- Guaranteed session durability across backend restart (best-effort reattach may work if exec survives and token remains valid).
- New public API versions.
- Frontend redesign.

## Sequencing and Dependencies (blocking rules)

- Phase 1 is a hard prerequisite for all sandbox traffic.
- Phase 2 must complete before enabling Phase 3 or Phase 4 for non-test traffic.
- Security controls for upstream calls (internal auth + SSRF guardrails + method/path allowlists) must be active before enabling sandbox HTTP delegation in Phase 3.
- Token issuance/validation and exec lifecycle policy must be active before enabling sandbox websocket delegation in Phase 4.
- Observability + readiness signals from Phase 5 are required before enabling sandbox mode outside controlled test environments.

## Hard Constraints

- No Sprites token in frontend payloads, query params, logs, or browser-facing errors.
- No client-controlled command execution in sandbox mode.
- Path traversal protections stay enforced.
- Feature behavior remains equivalent across local and sandbox modes.
- Multi-tenant sandbox mode is not supported unless session tokens are bound to authenticated user/workspace identity.

## Security Model (v0)

### Trust boundaries

- Browser is untrusted.
- Control plane is the only browser-facing entrypoint.
- Workspace service is a separate boundary even if currently private-network reachable.

### Internal auth

- Control plane to workspace service calls include internal auth (for example HMAC or signed internal token).
- Workspace service rejects unauthenticated requests.

### Proxy guardrails (SSRF prevention)

- `SpritesProxyClient` forwards only to allowlisted `host:port`, allowlisted path prefixes, and allowlisted methods.
- Never forward arbitrary URLs or client-supplied destinations.
- Disable redirect following (3xx treated as errors).
- Apply DNS pinning or resolved-IP allowlisting to reduce DNS rebinding risk.
- Strip hop-by-hop headers and never forward browser `Authorization` upstream.
- Enforce strict response size caps and content-length validation where feasible.

### Secrets hygiene

- Redact provider tokens, internal auth headers, and sensitive provider fields from logs/traces.
- Do not return raw upstream headers/bodies to browser errors.

### Resource caps and abuse controls

- Cap concurrent exec sessions.
- Cap output buffering per session.
- Enforce idle and absolute session timeouts.
- Define exec lifecycle policy:
  - websocket close defaults to detach (not terminate) for configurable reattach window
  - terminate on explicit exit, absolute timeout, or idle timeout beyond reattach window
  - periodic orphan GC reaps detached sessions past reattach window
- Add control-plane rate limits:
  - per-IP and per-user limits for WS connects/attaches
  - per-session input burst/rate limits
  - per-route limits for expensive endpoints (`/api/tree`, `/api/search`)

## Architecture

- Control plane remains the only browser-facing entrypoint.
- Workspace service handles filesystem/git/search/session HTTP operations.
- Sprites Exec handles interactive PTY/chat sessions.
- `WorkspaceGateway` selects local vs sandbox behavior and acts as anti-corruption boundary:
  - normalizes timeout/retry behavior
  - normalizes error mapping to stable browser-visible shapes
  - prevents provider-specific details from leaking into route handlers
  - enforces workspace-service compatibility via version handshake
- `SpritesGateway` composes service client + exec client + proxy client.

## Data Flow (explicit)

- HTTP (files/git/search/sessions) local mode:
  - browser -> control plane route -> local gateway/local handlers -> response
- HTTP (files/git/search/sessions) sandbox mode:
  - browser -> control plane route -> sandbox gateway -> sprites proxy/service client -> workspace service in sprite -> mapped response
- PTY websocket local mode:
  - browser `/ws/pty` -> control plane local PTY process bridge -> browser frames
- PTY websocket sandbox mode:
  - browser `/ws/pty` -> control plane WS bridge -> Sprites exec session -> browser frames
- Chat websocket local mode:
  - browser `/ws/claude-stream` -> control plane local chat runtime -> browser frames
- Chat websocket sandbox mode:
  - browser `/ws/claude-stream` -> control plane WS bridge -> Sprites exec session -> browser frames
- Session/reconnect identity flow in sandbox mode:
  - control plane creates exec session -> issues opaque `session_id` token -> browser reconnect sends token -> control plane validates token and attaches to exec -> success or `session_not_found`
- Failure handling flow (all sandbox paths):
  - provider/network/service failures are normalized at gateway boundary to existing HTTP and WS semantics (no raw upstream payloads)

## Internal Upstream Contract (control plane <-> workspace service)

- Define an internal API compatibility version (`X-Workspace-API-Version` or equivalent metadata).
- Control plane validates compatibility at startup.
- Incompatible versions fail fast with explicit diagnostics.
- Internal contract evolution requires backward-compatible window or coordinated deploy.

## Error Normalization (v0)

- Map upstream failures (workspace service/proxy/exec transport) to stable HTTP statuses and existing WS semantics (`error`, `session_not_found`).
- Do not surface raw upstream payloads/headers to browser clients.
- Retry policy is explicit:
  - retry only safe/idempotent calls
  - use bounded retries with jitter

## Compatibility Contract

### HTTP

- Keep `/api/tree`, `/api/file`, `/api/search`, `/api/git/*`, `/api/sessions` unchanged.
- `/api/sessions` remains schema-compatible; in v0 sandbox mode it is best-effort for active sessions visible to current control-plane instance (durable cross-restart catalog is out of scope).

### PTY websocket

- Keep `/ws/pty` route and current message envelope.
- Accept current frontend query params: `session_id`, `provider`, `resume`, `force_new`, `session_name`.
- Preserve `input`, `resize`, `ping` semantics.
- Preserve `session`, `history`, `output`, `error`, `exit`, `pong`, `session_not_found` responses.
- WS bridge requirements:
  - heartbeat/keepalive with configurable timeouts
  - bounded buffering and backpressure
  - explicit backpressure policy:
    - per-session max queue bytes/messages
    - on overflow, prefer controlled close with stable `error` semantics over unbounded memory growth
    - optional drop of non-essential frames (for example repeated resize) before output drop/close
  - fairness quotas so one hot session cannot starve loop time or memory
  - preserve framing semantics (avoid accidental transcoding bugs)
  - forward resize events immediately to exec session
  - normalize close codes/reasons so frontend behavior is consistent across modes

### Chat websocket

- Keep `/ws/claude-stream` route and current message envelope.
- Accept current query params and control message structure (including `session_id`, `mode`, `resume`, `force_new`, model/tool options).
- Preserve `system.connected` payload shape.
- In sandbox mode, return `session_id` as opaque session token.

## Session Identity (v0)

- `session_id` remains a string in existing payloads, but becomes opaque token.
- Token is signed (optional encryption) using `SESSION_TOKEN_SECRET`.
- Token payload conceptually includes:
  - `aud`
  - `provider`
  - `exec_id`
  - `kind`
  - `user_id`
  - `workspace_id`
  - `issued_at`
  - `expires_at`
- Token TTL is short (target 15-60 minutes) to reduce replay risk.
- Control plane validates and decodes token on attach; invalid/expired tokens map to existing `session_not_found` behavior.
- Token renewal can happen via existing `system.connected` flow without route/envelope changes.

## Edge Case Handling Matrix (required)

- Token expired/invalid at attach: return existing `session_not_found` semantics; do not leak token validation internals.
- Token expires while an active websocket is already attached: existing stream continues until disconnect; expiry only blocks new attach attempts.
- Token valid but upstream exec session missing: return `session_not_found`; frontend may create/restart session through existing behavior.
- Websocket disconnect beyond reattach window: session is terminated by lifecycle policy; reattach attempts resolve to `session_not_found`.
- Workspace service health flapping: circuit breaker transitions control retry behavior and returns stable mapped errors.
- Large binary file reads: return schema-compatible error/truncation behavior rather than raw binary data.

## Delivery Plan

## Phase 0 - Contract Baseline and Drift Fixes

- Snapshot current HTTP/WS contracts used by frontend.
- Fix known drift blockers before sandbox implementation.
- Remove ambiguous legacy codepaths from active composition.
- Promote snapshots into executable contract tests:
  - HTTP golden request/response tests for `/api/*`
  - WS frame-sequence tests for `/ws/pty` and `/ws/claude-stream` envelopes

Exit criteria:

- Local mode contract tests pass.
- Known drift blockers are closed.

## Phase 1 - Mode and Config

- Add `WORKSPACE_MODE=local|sandbox`.
- Add fixed sandbox env config (`SPRITES_BASE_URL`, `SPRITES_SPRITE_NAME`, token, service host/port/path).
- Add `SESSION_TOKEN_SECRET`.
- Add and validate deploy scripts under `deploy/sandbox/*`:
  - deployment script idempotency
  - restart script behavior
  - smoke check script output and non-zero exits on failure
- Add startup validation and clear errors:
  - validate required env vars
  - verify workspace service readiness via `/healthz`
  - verify internal compatibility via `/__meta/version`
  - fail fast with actionable diagnostics (auth vs unreachable vs bad path vs version mismatch)

Exit criteria:

- App boots deterministically in both modes.

## Phase 2 - Sandbox Gateway Foundation

- Implement `WorkspaceGateway` with local and sandbox implementations.
- Implement `SpritesServicesClient` for service reachability and endpoint resolution:
  - `resolve_endpoint()` with short TTL caching
  - `check_ready()` calling `/healthz` with bounded retries and jitter
  - small circuit-breaker behavior to avoid stampede when unhealthy
- Implement `SpritesExecClient` for create/attach/write/resize/terminate.
- Implement `SpritesProxyClient` for backend forwarding.
- Add normalized transport error mapping.

Exit criteria:

- Backend can reach workspace service and create/attach exec sessions.

## Phase 3 - HTTP Delegation

- Delegate files/git/search/session HTTP to workspace service in sandbox mode.
- Keep response schema compatibility.
- Performance/safety requirements:
  - stream file content responses where possible
  - enforce explicit size caps for file reads/uploads/search responses
  - bounded timeouts and idempotent-only retries
  - define large-repo behavior for `/api/tree` without route shape changes:
    - bounded traversal by max nodes, max depth, max time budget
    - degrade predictably with schema-compatible partial listing behavior

Exit criteria:

- File/git/search/session parity validated for local vs sandbox.

## Phase 4 - WebSocket Delegation via Exec

- Bridge `/ws/pty` to Sprites Exec in sandbox mode.
- Bridge `/ws/claude-stream` to Sprites Exec in sandbox mode.
- Issue/validate session tokens and map token to exec id on attach.
- Preserve reconnect and `session_not_found` behavior expected by frontend.
- Implement explicit bridge behaviors:
  - heartbeat timers and idle detection
  - bounded queues between browser WS and exec transport
  - deterministic teardown with documented reattach window
  - consistent error mapping (no raw provider errors)

Exit criteria:

- PTY/chat work in sandbox mode without frontend route changes.

## Phase 5 - Hardening and Tests

- Add structured logs and `request_id` correlation across relay boundaries.
- Propagate `request_id` for HTTP and WS handshake flows.
- Include `request_id` in workspace service and exec client calls where possible.
- Add explicit log-redaction policy and tests:
  - redact provider/internal auth/session token materials
  - do not log upstream error bodies verbatim unless safelisted
- Add core metrics:
  - workspace readiness duration and failure reasons
  - proxy request latency and status codes
  - exec attach failure count
  - WS disconnect count
- Add limits and cleanup for orphaned/idle exec sessions.
- Add control plane `/healthz` and `/readyz`:
  - `/healthz` covers liveness
  - `/readyz` covers readiness and returns structured dependency states in sandbox mode
  - include circuit-breaker state (`closed|half-open|open`) without leaking sensitive upstream details
- Add deterministic sandbox tests:
  - stub or record-replay Sprites clients for CI
  - gated live smoke tests when credentials exist
- Add fault-injection tests:
  - workspace service unhealthy (503)
  - transient exec attach failure
  - mid-stream WS disconnect

Exit criteria:

- Parity, boundary, resilience, and observability checks pass for v0 scope.

## Acceptance Criteria

- Config-only mode switch works.
- Browser behavior remains consistent.
- Sprites integration is backend-only.
- Chat and PTY in sandbox mode run on Exec.
- `session_id` remains stable and opaque (not raw provider id).
- Tokens stay server-side.

## Acceptance Criteria by Workstream (explicit, testable)

### Mode and config

- `WORKSPACE_MODE=local|sandbox` boots deterministically with validated config.
- Invalid sandbox config fails fast with actionable diagnostics.
- Script-based deploy workflow can bootstrap a clean sandbox runtime and pass smoke checks without manual steps.

### Security and policy

- Upstream workspace calls require internal auth and reject unauthenticated requests.
- SSRF guardrails block non-allowlisted host/path/method attempts.
- No provider/internal tokens appear in browser payloads or sanitized logs.
- Command template allowlist enforcement rejects non-allowlisted startup commands.
- Multi-tenant deployment is blocked unless authenticated identity binding for token scope is enabled.
- Deployment layout separation is enforced: workspace root excludes service runtime and secret paths.

### HTTP delegation

- `/api/tree`, `/api/file`, `/api/search`, `/api/git/*`, `/api/sessions` remain schema-compatible.
- Size caps/timeouts/retry policy behave as documented under normal and fault-injection tests.
- Large-repo traversal remains bounded and deterministic.

### Websocket delegation

- `/ws/pty` and `/ws/claude-stream` preserve message envelopes and semantics.
- Reattach within window succeeds at target rate; beyond window resolves deterministically (`session_not_found`).
- Backpressure policy enforces bounded memory without event-loop starvation.

### Observability and operations

- `/healthz` and `/readyz` expose liveness/readiness and structured dependency states.
- `request_id` propagates across control plane, workspace service, and exec operations.
- Core metrics cover readiness, proxy latency/status, exec attach failures, and WS disconnects.
- Initial SLO target measurements are captured in pre-release verification for sandbox mode.

## Post-V0 Roadmap (not required for V0 acceptance)

- Durable session registry (Redis or DB) plus key rotation strategy.
- Sandbox lifecycle APIs and service auto-provisioning.
- Per-user sandbox routing and multi-workspace mapping.
- Stronger auth/token refactor for end-to-end identity and isolation.
- Shadow/canary rollout strategy and rollback automation.
- Versioned public API (`/api/v1/*`) and deprecation policy.
- Additional remote provider support beyond Sprites.
- Artifact-based release packaging (wheel/build artifact) and rollback-friendly release management.
- Advanced observability (full OpenTelemetry tracing).
- `/api/tree` advanced optimizations (ETag/revalidation/cache-key strategy refinement).
