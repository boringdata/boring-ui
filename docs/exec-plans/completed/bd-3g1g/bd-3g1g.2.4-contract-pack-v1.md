# bd-3g1g.2.4 Contract Pack v1

Bead: `bd-3g1g.2.4`  
Version: `v1.0.0`  
Published: `2026-02-17` (UTC)  
Status: locked by `docs/bd-3g1g.2.4-signoff.md`

This document is the self-contained Phase-1 implementation contract baseline for service splits and control-plane boundaries. Maintainers should not need to reopen plan markdown to implement downstream beads.

## Canonical Service Ownership and Route Families

| Service | Canonical HTTP family (internal) | Canonical WS family (internal) | Frontend-callable directly | Boundary expectation |
|---|---|---|---|---|
| `workspace-core` | `/api/v1/files/*`, `/api/v1/git/*` | none | no | deny by default on missing scope/claims |
| `pty-service` | `/api/v1/pty/*` | `/ws/pty` | no | deny by default on missing scope/claims/session |
| `agent-normal` | `/api/v1/agent/normal/*` | `/ws/agent/normal/*` | no | runtime/session authority only |
| `agent-companion` | `/api/v1/agent/companion/*` | `/ws/agent/companion/*` | no | runtime/session authority only |
| `agent-pi` | `/api/v1/agent/pi/*` | `/ws/agent/pi/*` | no | runtime/session authority only |
| `control-plane` | `/auth/*`, `/api/v1/me`, `/api/v1/workspaces*`, `/w/{workspace_id}/*` | `/w/{workspace_id}/{path}` | yes | sole frontend boundary for auth + membership + policy |

## Frontend -> Control-Plane Contract (Only Direct UI Surface)

Only the following route families are frontend-callable directly:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/auth/login` | auth entrypoint |
| `GET` | `/auth/callback` | auth callback |
| `GET` | `/auth/logout` | session termination |
| `GET` | `/api/v1/me` | current user identity |
| `GET` | `/api/v1/workspaces` | list workspaces |
| `POST` | `/api/v1/workspaces` | create workspace |
| `GET` | `/api/v1/workspaces/{workspace_id}/runtime` | runtime status |
| `POST` | `/api/v1/workspaces/{workspace_id}/runtime/retry` | retry runtime provisioning |
| `GET` | `/api/v1/workspaces/{workspace_id}/settings` | read workspace settings metadata |
| `PUT` | `/api/v1/workspaces/{workspace_id}/settings` | write workspace settings metadata |
| `GET` | `/w/{workspace_id}/setup` | workspace setup surface |
| `GET/POST/PUT/PATCH/DELETE/HEAD/OPTIONS` | `/w/{workspace_id}/{path}` | workspace-scoped HTTP proxy boundary |
| `WS` | `/w/{workspace_id}/{path}` | workspace-scoped WebSocket proxy boundary |

## Reserved `/w/{workspace_id}/...` Route Precedence

1. Control-plane explicit subpaths are matched first (`setup`, `runtime`, `runtime/retry`, `settings`).
2. Remaining subpaths are evaluated as workspace-scoped proxy targets and must enforce session + membership policy.
3. Workspace proxy routing forwards only canonical workspace service families; unmatched/forbidden subpaths are denied by default.

## Not Frontend-Callable Directly

The frontend must not call these route families directly:

| Route family | Why denied at frontend boundary |
|---|---|
| `/api/v1/files/*` | internal `workspace-core` authority; must be mediated by control-plane workspace boundary |
| `/api/v1/git/*` | internal `workspace-core` authority; must be mediated by control-plane workspace boundary |
| `/api/v1/pty/*` | internal `pty-service` authority; direct UI access bypasses policy checks |
| `/ws/pty` | internal `pty-service` stream boundary |
| `/api/v1/agent/normal/*` | internal runtime family |
| `/ws/agent/normal/*` | internal runtime stream family |
| `/api/v1/agent/companion/*` | internal runtime family |
| `/ws/agent/companion/*` | internal runtime stream family |
| `/api/v1/agent/pi/*` | internal runtime family |
| `/ws/agent/pi/*` | internal runtime stream family |
| legacy direct `/api/*` and `/ws/*` without workspace scope | bypasses canonical control-plane auth/membership boundary |

## Scope/Capability Claim Requirements (`workspace-core`, `pty-service`)

Required claim-envelope fields for delegated file/git/pty operations:

| Field | Required | Contract |
|---|---|---|
| `request_id` | yes | trace correlation key |
| `workspace_id` | yes | workspace policy boundary |
| `actor` | yes | authenticated principal metadata |
| `capability_claims` | yes | explicit non-empty claims only |
| `cwd_or_worktree` | yes for file/git/pty | path/worktree scope boundary |
| `session_id` | yes for PTY runtime operations | PTY runtime/session correlation |

Required capability-claim baseline:

- `workspace.files.read`
- `workspace.files.write`
- `workspace.git.read`
- `workspace.git.write`
- `pty.session.start`
- `pty.session.attach`

Deny-by-default requirements:

1. Missing required scope fields is a hard deny.
2. Empty, unknown, or malformed `capability_claims` is a hard deny.
3. Missing operation-specific claim is a hard deny.
4. Workspace/session mismatch is a hard deny.
5. Validation occurs before side effects.

## Shared HTTP Error Envelope + Retry/Conflict Mutation Semantics

Canonical HTTP error envelope:

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

Phase-1 machine code baseline:

| Code | Retryable | Meaning |
|---|---|---|
| `invalid_scope_context` | false | required scope fields missing or malformed |
| `workspace_mismatch` | false | requested workspace outside authority scope |
| `session_mismatch` | false | requested session outside runtime scope |
| `capability_denied` | false | claims missing/invalid/insufficient |
| `conflict_in_flight` | true | equivalent mutation already in progress |
| `idempotency_replay` | false | idempotency key matched prior completed operation |
| `upstream_unavailable` | true | dependency unavailable with safe retry contract |

Mutation contract baseline:

| Operation class | Idempotency contract | Conflict contract |
|---|---|---|
| create/queue (`POST`) | idempotency key required for side-effecting operations | duplicate key returns prior outcome (`idempotency_replay`) |
| write/rename/move/delete | retries must not duplicate side effects | deterministic non-retryable conflict/forbidden envelope |
| runtime retry/start | dedupe per workspace/session where applicable | in-flight duplicates return `conflict_in_flight` |

## Governance and Revision Policy

1. This contract pack (`v1.0.0`) is the Phase-1 baseline for downstream implementation beads.
2. Any contract change requires an explicit revision bead (for example `bd-3g1g.2.4-rN`) with reviewer sign-off.
3. Downstream phases must treat this pack and its sign-off record as the normative baseline.
