# bd-3g1g.2.3 API Standards Note

Bead: `bd-3g1g.2.3`  
Depends on: `bd-3g1g.2.2`

Goal: standardize one HTTP error envelope and one retry-safe mutation contract across `workspace-core`, `pty-service`, and agent runtime services.

## Canonical HTTP Error Envelope (normative)

All HTTP APIs in scope MUST return this shape for non-2xx responses:

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

Required rules:

1. `code` is stable and policy-usable by clients.
2. `message` is safe for direct UI fallback text.
3. `retryable` is set by contract semantics, not guessed from transport class.
4. `details` MUST include correlation fields needed for triage.

## Standard Error Code Set (phase-1 baseline)

| Code | Retryable | Meaning |
|---|---|---|
| `invalid_scope_context` | false | required scope fields missing or malformed |
| `workspace_mismatch` | false | requested workspace does not match authority scope |
| `session_mismatch` | false | requested session does not match active/runtime scope |
| `capability_denied` | false | capability claims are missing/invalid/insufficient |
| `conflict_in_flight` | true | concurrent operation already in progress |
| `idempotency_replay` | false | idempotency key matched prior completed operation |
| `upstream_unavailable` | true | dependency unavailable with safe retry contract |

## Mutation Semantics (normative)

| Operation class | Idempotency contract | Conflict contract |
|---|---|---|
| create/queue (`POST`) | idempotency key required for side-effecting operations | duplicate key returns prior outcome (`idempotency_replay`) |
| write/rename/move/delete | retries MUST not duplicate side effects | scope/path conflicts return deterministic non-retryable envelope |
| runtime retry/start | dedupe per workspace/session where applicable | in-flight duplicates return `conflict_in_flight` |

Required mutation rules:

1. mutations are either idempotent by key or deterministic by contract.
2. side effects MUST happen after scope/capability validation.
3. repeated requests cannot create divergent state for the same idempotency context.
4. retryability is explicitly encoded in envelope response.

## Service Adoption Matrix

| Service | Error envelope adoption | Mutation semantics adoption |
|---|---|---|
| `workspace-core` | required | required |
| `pty-service` | required | required |
| `agent-normal` | required | required for runtime/session mutations |
| `agent-companion` | required | required for runtime/session mutations |
| `agent-pi` | required | required for runtime/session mutations |

## Contract Governance

1. This note is normative for Phase-1 and downstream implementation beads.
2. Any addition/removal of error codes or mutation classes requires an explicit contract revision bead.
3. Service-specific docs may extend examples but may not contradict this note.
