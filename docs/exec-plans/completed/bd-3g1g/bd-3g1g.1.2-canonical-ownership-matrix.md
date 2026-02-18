# bd-3g1g.1.2 Canonical Ownership Matrix

Bead: `bd-3g1g.1.2`  
Depends on: `bd-3g1g.1.1` inventory artifact (`docs/ROUTE_CALLSITE_INVENTORY_bd-3g1g.1.1.md`)

Goal: provide an authoritative `current -> canonical -> owner -> disposition` matrix with explicit policy notes.

Owner vocabulary in this matrix:
- `front`
- `workspace-core`
- `pty-service`
- `agent-normal`
- `agent-companion`
- `agent-pi`
- `control-plane`

Route status vocabulary:
- `canonical`
- `legacy`
- `dead`

Migration action vocabulary:
- `keep`
- `rewrite`
- `remove`
- `delegate`

## Ownership Matrix

| Current family | Canonical target family | Canonical owner | Route status | Migration action | Policy notes |
|---|---|---|---|---|---|
| `/health` | `/health` | `workspace-core` | `canonical` | `keep` | Internal service liveness endpoint; no workspace mutation surface. |
| `/api/capabilities` | `/api/capabilities` | `workspace-core` | `canonical` | `keep` | Capability publication boundary for front gating; no privileged side effects. |
| `/api/config` | `/api/config` | `workspace-core` | `canonical` | `keep` | Runtime bootstrap metadata only; no auth/session bypass semantics. |
| `/api/project` | `/api/project` | `workspace-core` | `canonical` | `keep` | Runtime project-root bootstrap endpoint only. |
| `/api/sessions` | `/api/v1/agent/normal/sessions` | `agent-normal` | `legacy` | `rewrite` | Runtime/session API only; file/git/pty side effects must delegate to workspace-core/pty-service. |
| `/api/approval/request` | `/api/approval/request` | `workspace-core` | `canonical` | `keep` | Approval boundary with deny-by-default policy enforcement. |
| `/api/approval/pending` | `/api/approval/pending` | `workspace-core` | `canonical` | `keep` | Approval listing remains within workspace authority boundary. |
| `/api/approval/decision` | `/api/approval/decision` | `workspace-core` | `canonical` | `keep` | Decision handling enforces workspace policy/authz constraints. |
| `/api/approval/status/{request_id}` | `/api/approval/status/{request_id}` | `workspace-core` | `canonical` | `keep` | Approval state read must stay inside workspace policy boundary. |
| `/api/approval/{request_id}` | `/api/approval/{request_id}` | `workspace-core` | `canonical` | `keep` | Deletion/cancellation remains policy-gated at workspace boundary. |
| `/api/v1/files/list` | `/api/v1/files/list` | `workspace-core` | `canonical` | `keep` | Files authority endpoint; workspace scope + capability claims enforced at owner. |
| `/api/v1/files/read` | `/api/v1/files/read` | `workspace-core` | `canonical` | `keep` | Files authority endpoint; read policy enforced at workspace-core boundary. |
| `/api/v1/files/write` | `/api/v1/files/write` | `workspace-core` | `canonical` | `keep` | Files mutation endpoint; deny-by-default capability enforcement required. |
| `/api/v1/files/delete` | `/api/v1/files/delete` | `workspace-core` | `canonical` | `keep` | Files mutation endpoint; workspace ownership + policy checks required. |
| `/api/v1/files/rename` | `/api/v1/files/rename` | `workspace-core` | `canonical` | `keep` | Files mutation endpoint; path policy validation enforced at owner. |
| `/api/v1/files/move` | `/api/v1/files/move` | `workspace-core` | `canonical` | `keep` | Files mutation endpoint; workspace policy checks at workspace-core boundary. |
| `/api/v1/files/search` | `/api/v1/files/search` | `workspace-core` | `canonical` | `keep` | Files search endpoint; scope restrictions enforced at owner boundary. |
| `/api/v1/git/status` | `/api/v1/git/status` | `workspace-core` | `canonical` | `keep` | Git authority endpoint; no duplicate ownership in agent services. |
| `/api/v1/git/diff` | `/api/v1/git/diff` | `workspace-core` | `canonical` | `keep` | Git authority endpoint; workspace scope and permission checks at owner. |
| `/api/v1/git/show` | `/api/v1/git/show` | `workspace-core` | `canonical` | `keep` | Git authority endpoint; policy checks remain centralized in workspace-core. |
| `/ws/pty` | `/ws/pty` | `pty-service` | `canonical` | `keep` | PTY/WebSocket authority boundary; session/provider validation at pty-service. |
| `/ws/claude-stream` | `/api/v1/agent/normal/stream` | `agent-normal` | `legacy` | `rewrite` | Runtime stream endpoint only; no direct file/git/pty mutation ownership. |
| `/api/x/{plugin}/...` | `/api/x/{plugin}/...` | `workspace-core` | `canonical` | `keep` | Optional workspace plugin surface gated by allowlist + runtime policy. |
| `/ws/plugins` | `/ws/plugins` | `workspace-core` | `canonical` | `keep` | Plugin change-notification channel; no workspace authority bypass. |
| `/api/tree` | `/api/v1/files/list` | `workspace-core` | `legacy` | `remove` | Legacy alias removed after canonical v1 cutover for files list. |
| `/api/file` | `/api/v1/files/{read,write,delete}` | `workspace-core` | `legacy` | `remove` | Legacy multi-method alias replaced by canonical v1 file endpoints. |
| `/api/file/rename` | `/api/v1/files/rename` | `workspace-core` | `legacy` | `remove` | Legacy alias removed; canonical v1 rename is source of truth. |
| `/api/file/move` | `/api/v1/files/move` | `workspace-core` | `legacy` | `remove` | Legacy alias removed; canonical v1 move is source of truth. |
| `/api/search` | `/api/v1/files/search` | `workspace-core` | `legacy` | `remove` | Legacy alias removed; canonical v1 search endpoint retained. |
| `/api/git/status` | `/api/v1/git/status` | `workspace-core` | `legacy` | `remove` | Legacy git prefix removed; canonical v1 git family retained. |
| `/api/git/diff` | `/api/v1/git/diff` | `workspace-core` | `legacy` | `remove` | Legacy git prefix removed; canonical v1 git family retained. |
| `/api/git/show` | `/api/v1/git/show` | `workspace-core` | `legacy` | `remove` | Legacy git prefix removed; canonical v1 git family retained. |
| `/api/attachments` | `/api/v1/agent/normal/attachments` | `agent-normal` | `legacy` | `rewrite` | Attachment ingress belongs to runtime service; delegated workspace side effects only. |
| `/api/fs/{list,home}` | `/api/v1/agent/companion/fs/*` | `agent-companion` | `legacy` | `rewrite` | Companion runtime endpoint family; workspace side effects must delegate out. |
| `/api/envs{,/{slug}}` | `/api/v1/agent/companion/envs/*` | `agent-companion` | `legacy` | `rewrite` | Companion runtime config surface; keep within agent-companion boundary. |
| `/api/git/{repo-info,branches,worktrees,worktree,fetch,pull}` | `/api/v1/agent/companion/git/*` | `agent-companion` | `legacy` | `rewrite` | Companion git tooling surface; authoritative git mutations remain workspace-core owned. |
| `/ws/browser/{session_id}` | `/api/v1/agent/companion/stream/*` | `agent-companion` | `legacy` | `rewrite` | Companion stream channel remains runtime-only boundary with delegated side effects. |
| `/api/sessions/create` | `/api/v1/agent/pi/sessions/create` | `agent-pi` | `legacy` | `rewrite` | PI runtime lifecycle surface; policy and side effects delegated to workspace-core/pty-service. |
| `/api/sessions/{id}/history` | `/api/v1/agent/pi/sessions/{id}/history` | `agent-pi` | `legacy` | `rewrite` | PI runtime history endpoint; no direct workspace authority ownership. |
| `/api/sessions/{id}/stream` | `/api/v1/agent/pi/sessions/{id}/stream` | `agent-pi` | `legacy` | `rewrite` | PI runtime stream endpoint; file/git/pty operations must delegate. |
| `/api/v1/me` | `/api/v1/me` | `control-plane` | `canonical` | `keep` | Session cookie identity endpoint enforced at control-plane boundary. |
| `/api/v1/workspaces` | `/api/v1/workspaces` | `control-plane` | `canonical` | `keep` | Workspace list/create endpoint with control-plane auth/membership checks. |
| `/api/v1/workspaces/{workspace_id}/runtime` | `/api/v1/workspaces/{workspace_id}/runtime` | `control-plane` | `canonical` | `keep` | Runtime status endpoint with workspace membership validation. |
| `/api/v1/workspaces/{workspace_id}/runtime/retry` | `/api/v1/workspaces/{workspace_id}/runtime/retry` | `control-plane` | `canonical` | `keep` | Runtime retry endpoint with control-plane policy enforcement. |
| `/api/v1/workspaces/{workspace_id}/settings` | `/api/v1/workspaces/{workspace_id}/settings` | `control-plane` | `canonical` | `keep` | Workspace settings endpoint under control-plane auth/membership boundary. |
| `/auth/login` | `/auth/login` | `control-plane` | `canonical` | `keep` | Public auth entrypoint controlled by control-plane auth subsystem. |
| `/auth/callback` | `/auth/callback` | `control-plane` | `canonical` | `keep` | Auth callback/session issuance remains control-plane owned. |
| `/auth/logout` | `/auth/logout` | `control-plane` | `canonical` | `keep` | Session termination remains control-plane owned. |
| `/w/{workspace_id}/setup` | `/w/{workspace_id}/setup` | `control-plane` | `canonical` | `keep` | Workspace onboarding route with control-plane membership checks. |
| `/w/{workspace_id}/{path}` | `/w/{workspace_id}/{path}` | `control-plane` | `canonical` | `keep` | Canonical workspace HTTP/WS proxy boundary with policy enforcement. |
| `/api/v1/agent/normal/*` | `/api/v1/agent/normal/*` | `agent-normal` | `canonical` | `keep` | Canonical runtime/service boundary; workspace and PTY side effects delegated. |
| `/api/v1/agent/companion/*` | `/api/v1/agent/companion/*` | `agent-companion` | `canonical` | `keep` | Canonical runtime/service boundary; workspace and PTY side effects delegated. |
| `/api/v1/agent/pi/*` | `/api/v1/agent/pi/*` | `agent-pi` | `canonical` | `keep` | Canonical runtime/service boundary; workspace and PTY side effects delegated. |

## Coverage Checkpoints

1. Every route family in `docs/ROUTE_CALLSITE_INVENTORY_bd-3g1g.1.1.md` Route Family Ledger appears in this matrix.
2. Every row has owner, target family, status, action, and policy notes.
3. Every row uses approved status/action vocabularies to stay execution-ready for follow-on phase beads.
