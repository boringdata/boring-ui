# bd-3g1g Phase-1 Contract Freeze

Bead: `bd-3g1g.2`  
Scope: freeze canonical contracts for `workspace-core`, `pty-service`, and agent services, plus frontend control-plane interface commitments.

Publication baseline: downstream implementation should consume
`docs/bd-3g1g.2.4-contract-pack-v1.md` and `docs/bd-3g1g.2.4-signoff.md`
as the locked Phase-1 contract package.

## Inputs and Dependencies

Contract freeze is based on:

- `docs/SERVICE_SPLIT_AND_LEGACY_CLEANUP_PLAN.md`
- `docs/ROUTE_CALLSITE_INVENTORY_bd-3g1g.1.1.md`
- `docs/bd-3g1g-phase0-baseline.md`
- closed implementation evidence from `bd-3g1g.5.1` (legacy file/git cutover)

Policy constraints preserved:

1. feature code must not hardcode control-plane route schema.
2. frontend uses shared transport helpers only.
3. no long-lived compatibility layer or dual-route fallback.
4. file/git side effects remain at `workspace-core`; PTY side effects remain at `pty-service`.

## Canonical Route Prefix Freeze

### Service ownership prefixes (normative)

| Service | Canonical HTTP prefix | Canonical WS prefix | Notes |
|---|---|---|---|
| `workspace-core` | `/api/v1/files/*`, `/api/v1/git/*` | none | sole file/git authority |
| `pty-service` | `/api/v1/pty/*` (lifecycle metadata) | `/ws/pty` | PTY session + terminal stream authority |
| `agent-normal` | `/api/v1/agent/normal/*` | `/ws/agent/normal/*` | runtime/session/stream only |
| `agent-companion` | `/api/v1/agent/companion/*` | `/ws/agent/companion/*` | runtime/session/orchestration only |
| `agent-pi` | `/api/v1/agent/pi/*` | `/ws/agent/pi/*` | runtime/session/history/stream only |
| `control-plane` (frontend callable) | `/auth/*`, `/api/v1/me`, `/api/v1/workspaces*`, `/w/{workspace_id}/*` | `/w/{workspace_id}/{path}` | gateway/auth/membership policy boundary |

### Current-to-canonical route-family decisions

| Current family | Canonical family | Disposition |
|---|---|---|
| `/api/sessions` (runtime app) | `/api/v1/agent/normal/sessions*` | rewrite |
| `/ws/claude-stream` | `/ws/agent/normal/stream` | rewrite |
| `/api/attachments` | `/api/v1/agent/normal/attachments` | rewrite |
| companion direct `/api/*` and `/ws/browser/*` | `/api/v1/agent/companion/*` and `/ws/agent/companion/*` | rewrite |
| PI direct `/api/sessions*` | `/api/v1/agent/pi/*` | rewrite |
| `/api/v1/files/*`, `/api/v1/git/*`, `/ws/pty` | same | keep |
| `/api/tree`, `/api/file*`, `/api/search`, `/api/git/*` (legacy) | canonical v1 families above | remove |

## Shared Scope and Capability Context

All service-owned mutation/runtime operations MUST evaluate these context fields:

| Field | Type | Required | Enforcement owner | Notes |
|---|---|---|---|---|
| `request_id` | string | yes | all services | traceable request correlation |
| `workspace_id` | string | yes | control-plane + service owners | membership and workspace scoping |
| `session_id` | string | yes for runtime/pty; optional where documented for bootstrap | agent services + pty-service | runtime correlation key |
| `actor` | object `{user_id, service, role}` | yes | all services | authn/authz principal |
| `capability_claims` | list[string] | yes | `workspace-core`, `pty-service` | deny-by-default on missing claims |
| `cwd_or_worktree` | string | required for file/git/pty ops | owning service | path/worktree boundary |
| `provider` | string | required for agent-runtime/pty start | owning runtime service | provider routing and policy |

Capability claim baseline:

1. write operations require explicit write claim.
2. PTY start/attach requires PTY claim.
3. owner service validates claims even when caller is another internal service.
4. denials return canonical error envelope.

## HTTP Error Envelope Freeze

All HTTP APIs covered by this phase return:

```json
{
  "code": "string_machine_code",
  "message": "human readable summary",
  "retryable": false,
  "details": {
    "request_id": "req_...",
    "workspace_id": "ws_..."
  }
}
```

Envelope requirements:

1. `code` is stable for client policy logic.
2. `message` is safe for user-facing fallback copy.
3. `retryable` is policy-directed (not transport-guessing).
4. `details` includes at least correlation context needed for triage.

Normative detail source: `docs/bd-3g1g.2.3-api-standards-note.md`.

## Mutation Semantics Freeze

| Operation class | Idempotency expectations | Conflict semantics |
|---|---|---|
| create/queue (`POST`) | client idempotency key required when operation has side effects beyond immediate request | duplicate key returns existing operation outcome |
| write/rename/move/delete | retries must not produce duplicated side effects | path/workspace mismatch returns deterministic conflict/forbidden envelope |
| runtime retry/start | dedupe per workspace/session where applicable | concurrent in-flight operation returns conflict envelope |

Normative detail source: `docs/bd-3g1g.2.3-api-standards-note.md`.

## Contract Governance and Sign-Off

Change control:

1. any prefix or envelope change requires explicit Phase-1 contract revision.
2. downstream implementation beads (`bd-3g1g.3+`) consume this document as normative contract source.
3. legacy aliases are transitional only and must not be reintroduced after Phase-5 cutover.

Sign-off record:

| Sign-off item | Evidence |
|---|---|
| Phase-0 inventory baseline available | `docs/ROUTE_CALLSITE_INVENTORY_bd-3g1g.1.1.md`, `docs/bd-3g1g-phase0-baseline.md` |
| Phase-1 contract freeze published | this document (`docs/bd-3g1g-phase1-contract-freeze.md`) |
| Route-family ambiguity removed for normal/companion/pi, workspace-core, pty-service | canonical prefix tables above |
| Approval recorded by implementing agent | `CoralDog` (Agent Mail + bead history) |

Exit-gate checklist for `bd-3g1g.2`:

1. canonical prefixes are explicitly frozen.
2. shared scope/capability context is explicitly defined.
3. error envelope and mutation semantics are explicitly defined.
4. sign-off record and governing policy are documented.
