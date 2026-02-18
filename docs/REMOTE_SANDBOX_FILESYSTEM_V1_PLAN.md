# Remote Sandbox Filesystem Plan (V1)

## Goal

Evolve v0 into a production-grade multi-sandbox platform with strong reliability, security, and operational controls, while preserving the same frontend contract.

## V1 Objectives

- Add sandbox management API for dynamic sandbox selection and lifecycle.
- Remove hardcoded sandbox target from control-plane runtime.
- Keep local/sandbox behavior consistent for file, git, and chat workflows.
- Improve resilience for reconnect, restarts, and temporary provider outages.
- Keep provider abstraction extensible beyond Sprites.
- Add safe production rollout controls (shadow, canary, rollback automation).
- Add token key rotation and stronger multi-tenant identity binding.
- Add periodic upstream compatibility checks beyond startup validation.
- Add full observability stack (OpenTelemetry tracing + metrics dashboards).
- Add advanced large-repo optimization for `/api/tree` (cache + revalidation strategy).

## Key Changes from V0

- Introduce sandbox management plane (`/api/sandbox/*`) for create/start/stop/status.
- Add `TargetResolver` backed by sandbox metadata instead of static env-only target.
- Add persistent session registry for interactive sessions.
- Keep browser route compatibility, but decouple browser session identity from provider-native exec ids internally.
- Add authenticated/authorized sandbox operations and audit trails.
- Move deployment from script-first source sync to artifact-based releases (wheel/build artifact) with safer rollback semantics.
- Move from basic token signing to `kid`-based key rotation and managed rotation lifecycle.
- Move from startup-only compatibility checks to startup + periodic runtime checks.
- Move from basic logging/metrics to end-to-end OpenTelemetry traces and SLO dashboards.
- Move from capped `/api/tree` traversal only to cache/revalidation optimizations (ETag/conditional fetch where applicable).
- Introduce controlled rollout modes (shadow/canary) and rollback automation as standard operations.

## Scope

### In scope

- Sandbox lifecycle API and internal orchestration.
- Dynamic target resolution by workspace/user/session.
- Persistent mapping of session metadata and reconnect state.
- Graceful failure handling for service unavailability and stale sessions.
- Operational guardrails and SLO-focused observability.
- Shadow/canary rollout strategy and rollback automation.
- Token key rotation, key versioning, and stricter session token scope controls.
- Periodic workspace-service compatibility checks with fail-fast behavior on drift.
- Advanced `/api/tree` performance strategy for large repositories.

### Out of scope

- Full multi-provider feature parity in first v1 slice.
- Deep frontend UX redesign.
- Cross-region orchestration and global traffic routing.

## Architecture Direction

- Keep control-plane and workspace-runtime split.
- Add dedicated sandbox orchestration components.
- Keep Sprites as first provider with provider-neutral interfaces.

## Core Components

- `SandboxManager` for lifecycle orchestration.
- `TargetResolver` for runtime endpoint selection.
- `WorkspaceGateway` for route-level local/sandbox dispatch.
- `SessionStore` for durable interactive session metadata.
- `SpritesProviderAdapter` implementing provider-neutral contracts.

## Data and Identity Model

- Introduce canonical internal session record with fields:
- `session_id` (frontend-facing stable id).
- `provider_session_id` (Sprites exec id).
- `workspace_id`.
- `mode`.
- `created_at`, `last_seen_at`, `status`.
- Allow compatibility mode where `session_id == provider_session_id` during migration.
- Introduce managed key metadata for token signing/verification:
- `kid`, `active_from`, `deprecates_at`, `expires_at`.
- Bind token identity scope to authenticated principal and workspace in multi-tenant mode.

## Reliability Plan

- Health checks for workspace service endpoint and exec channel readiness.
- Retry policy with jitter for transient provider/network failures.
- Circuit-breaker behavior for repeated upstream failures.
- Deterministic reconnect semantics with explicit state machine.
- Janitor tasks for orphaned sessions and stale mappings.
- Periodic compatibility probe for workspace-service version contract (not just startup).

## Performance Plan

- Shared connection pools for outbound HTTP/proxy calls.
- Backpressure-aware websocket pumps with bounded queues.
- Stream processing without redundant JSON re-encoding where possible.
- Metrics-driven tuning for timeout and buffer thresholds.
- `/api/tree` large-repo strategy:
- bounded traversal + caching keyed by repo/path state.
- conditional revalidation semantics (ETag/If-None-Match or equivalent internal freshness strategy).

## Security Plan

- Server-only token custody with secret redaction by default.
- Capability-based permission checks on sandbox lifecycle endpoints.
- Audit logs for lifecycle and exec operations.
- Strict input validation for all user-influenced sandbox parameters.
- Policy checks for allowed command profiles and workspace boundaries.
- Key rotation policy for session/auth tokens with overlap window and revocation path.
- Multi-tenant enforcement: no fallback single-tenant identity mode in multi-tenant deployments.

## API and Contract Strategy

- Keep existing browser routes stable for files/git/sessions/ws.
- Add sandbox management endpoints without breaking existing routes.
- Preserve PTY/chat message contracts expected by frontend.
- Add explicit typed error codes for sandbox-related failures.
- Add internal compatibility contract versioning with periodic drift detection and explicit operator-facing diagnostics.

## Delivery Plan

## Phase 1 - Sandbox Management Foundations

- Add sandbox metadata model and persistence.
- Add lifecycle endpoints and orchestration skeleton.
- Add authz and audit hooks.
- Add controlled rollout primitives (`shadow`, canary routing controls, rollback hooks).

Exit criteria:

- Sandbox target is no longer hardcoded and can be resolved dynamically.
- Shadow routing can compare/observe parity without browser contract changes.

## Phase 2 - Session Durability and Reconnect State Machine

- Add persistent session store for PTY/chat session metadata.
- Implement reconnect policy and stale-session recovery.
- Maintain frontend compatibility throughout.
- Introduce token key versioning (`kid`) and rotation-safe validation path.

Exit criteria:

- Reconnect survives control-plane restart for supported scenarios.
- Token rotation can occur without breaking active sessions within policy window.

## Phase 3 - Reliability and Performance Hardening

- Add retries/circuit-breakers/time budgets.
- Add backpressure controls and queue limits.
- Add complete metrics/tracing dashboards.
- Add periodic compatibility checks for workspace-service version contract.
- Implement advanced `/api/tree` optimization strategy for large repositories.

Exit criteria:

- Error-rate and latency targets are measurable and within agreed thresholds.
- Compatibility drift is detected automatically and surfaced with actionable diagnostics.

## Phase 4 - Security and Compliance Hardening

- Complete audit coverage.
- Add policy enforcement tests and secret-leak regression checks.
- Add operator playbooks for incident response.
- Enforce key rotation runbooks and recovery paths.
- Enforce multi-tenant identity binding policies.

Exit criteria:

- Security controls are test-verified and operationally documented.

## Phase 5 - Rollout and Operations

- Execute staged rollout playbook:
- shadow validation -> canary -> progressive expansion.
- Enforce SLO/error-budget gates for promotion between rollout stages.
- Validate automated rollback controls and drills.

Exit criteria:

- Rollout and rollback paths are tested, repeatable, and operator-approved.

## Acceptance Criteria

- Dynamic sandbox selection works via management API.
- Browser contract remains unchanged for existing features.
- Session recovery is robust and measurable.
- Provider adapters remain swappable.
- Reliability, performance, and security targets are tracked and met.
- Token key rotation works without breaking valid active sessions.
- Periodic compatibility checks detect upstream drift before user-facing breakage.
- Advanced `/api/tree` strategy improves large-repo behavior while preserving response compatibility.
- Shadow/canary rollout and rollback controls are production-ready.
