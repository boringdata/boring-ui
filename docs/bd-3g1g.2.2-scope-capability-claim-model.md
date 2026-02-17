# bd-3g1g.2.2 Scope/Capability Claim Model

Bead: `bd-3g1g.2.2`  
Depends on: `bd-3g1g.2.1` finalized canonical prefixes

Goal: define the shared claim envelope and the deny-by-default validation contract enforced by `workspace-core` and `pty-service`.

## Claim Envelope (normative)

Every delegated file/git/pty operation MUST carry a claim envelope with these fields:

| Field | Type | Required | Notes |
|---|---|---|---|
| `request_id` | string | yes | trace/correlation key |
| `workspace_id` | string | yes | workspace policy boundary |
| `actor` | object `{user_id, service, role}` | yes | authenticated principal |
| `capability_claims` | list[string] | yes | explicit permission claims, never implicit |
| `cwd_or_worktree` | string | yes for file/git/pty operations | path/worktree authority boundary |
| `session_id` | string | required for PTY runtime operations | runtime/session correlation key |

Validation precondition:

1. Any missing required field is a hard validation failure.
2. `capability_claims` MUST be non-empty and contain only recognized claims.
3. Unknown or malformed claims are denied as policy violations.

## Capability Claim Registry (phase-1 baseline)

| Claim | Owner service | Required for |
|---|---|---|
| `workspace.files.read` | `workspace-core` | list/read/search file endpoints |
| `workspace.files.write` | `workspace-core` | write/rename/move/delete file endpoints |
| `workspace.git.read` | `workspace-core` | git status/diff/show endpoints |
| `workspace.git.write` | `workspace-core` | mutating git operations (if enabled) |
| `pty.session.start` | `pty-service` | PTY session create/start operations |
| `pty.session.attach` | `pty-service` | PTY attach/stream operations |

Phase-1 policy:

1. Claims are additive and explicit; no wildcard claim grants.
2. Internal service-to-service calls do not bypass claim checks.
3. Missing required claim always resolves to deny.

## Deny-By-Default Enforcement Contract

### `workspace-core` rules (normative)

1. `workspace-core` MUST reject requests when `workspace_id` is absent or does not match the target resource scope.
2. Read paths (`list`, `read`, `search`, `git status/diff/show`) require `workspace.files.read` or `workspace.git.read` as applicable; otherwise deny.
3. Mutation paths (`write`, `rename`, `move`, `delete`, mutating git operations) require explicit write claims; read-only claims are insufficient.
4. If claims are missing, malformed, empty, or unknown, `workspace-core` returns policy denial and performs no side effects.
5. Validation runs before filesystem/git execution and before delegation to any lower-level helper.

### `pty-service` rules (normative)

1. `pty-service` MUST reject requests when `workspace_id` is absent or mismatched to the PTY session workspace.
2. PTY start/create requires `pty.session.start`; requests without this claim are denied.
3. PTY attach/stream requires `pty.session.attach` and a valid `session_id`; either missing element is denied.
4. Unknown claims, empty claim sets, or malformed claim payloads are denied before PTY process creation/attach.
5. Internal callers (including agent services and control-plane delegates) are still subject to the same claim checks.

## Required Denial Outcomes

Both `workspace-core` and `pty-service` MUST deny by default and must not execute side effects when any of the following is true:

1. claim envelope is missing required fields.
2. `capability_claims` is empty.
3. required operation claim is absent.
4. claim value is unknown/malformed.
5. workspace/session scope does not match the target operation.

Minimum machine-code expectations for phase-1 deny paths:

- `invalid_scope_context`
- `capability_denied`
- `workspace_mismatch`
- `session_mismatch`

This artifact is normative for downstream implementation beads that wire shared claim middleware and owner-service validators.
