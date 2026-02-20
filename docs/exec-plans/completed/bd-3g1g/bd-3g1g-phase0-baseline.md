# bd-3g1g Phase-0 Baseline

Bead: `bd-3g1g.1`  
Scope: baseline mapping + executable dependency-aware work breakdown for service split / control-plane decoupling / legacy cutover.

## Snapshot Inputs

Data in this baseline was collected from current `HEAD` (`b5552ff`) using:

- `python3` route introspection over `create_app()`
- route/callsite grep scans across `src/`, `tests/`, `docs/`, `scripts/`
- bead dependency extraction from `.beads/issues.jsonl`

This is an auditable point-in-time baseline. Later commits in this branch may already migrate some listed legacy callsites; treat this file as the phase-0 starting snapshot, not a continuously updated live state document.

Primary source files scanned:

- `src/back/boring_ui/api/app.py`
- `src/back/boring_ui/api/modules/files/router.py`
- `src/back/boring_ui/api/modules/git/router.py`
- `src/back/boring_ui/api/modules/pty/router.py`
- `src/back/boring_ui/api/modules/stream/router.py`
- `src/front/App.jsx`
- `src/front/components/FileTree.jsx`
- `src/front/panels/EditorPanel.jsx`
- `src/front/components/GitChangesView.jsx`
- `src/front/components/Terminal.jsx`
- `src/front/components/chat/ClaudeStreamChat.jsx`
- `src/front/providers/pi/backendAdapter.jsx`
- `src/front/providers/companion/upstream/api.ts`
- `src/front/providers/companion/upstream/ws.ts`
- `src/pi_service/server.mjs`
- `tests/integration/test_create_app.py`
- `docs/SERVICE_SPLIT_AND_LEGACY_CLEANUP_PLAN.md`

## Route and Callsite Inventory

### Runtime routes currently exposed by `create_app()`

- `GET /api/v1/files/list`
- `GET /api/v1/files/read`
- `PUT /api/v1/files/write`
- `DELETE /api/v1/files/delete`
- `POST /api/v1/files/rename`
- `POST /api/v1/files/move`
- `GET /api/v1/files/search`
- `GET /api/v1/git/status`
- `GET /api/v1/git/diff`
- `GET /api/v1/git/show`
- `WS /ws/pty`
- `WS /ws/claude-stream`
- `GET /api/capabilities`
- `GET /api/config`
- `GET /api/project`
- `GET /api/sessions`
- `POST /api/sessions`
- `POST /api/approval/request`
- `GET /api/approval/pending`
- `POST /api/approval/decision`
- `GET /api/approval/status/{request_id}`
- `DELETE /api/approval/{request_id}`

### Frontend and service callsite families still referenced

- Legacy/local runtime families: `/api/tree`, `/api/file`, `/api/file/rename`, `/api/file/move`, `/api/search`, `/api/git/*`
- Stream/terminal families: `/ws/claude-stream`, `/ws/pty`, `/ws/plugins`
- Runtime session families: `/api/sessions`, `/api/sessions/create`, `/api/sessions/{id}/history`, `/api/sessions/{id}/stream`, `/api/sessions/{id}/stop`
- Companion direct-connect families: `/api/*` + `/ws/browser/{sessionId}` (service-local base)
- Control-plane contract families in docs/plan: `/api/v1/me`, `/api/v1/workspaces*`, `/auth/logout`, `/w/{workspace_id}/*`
- Unresolved in-repo callsite family: `/api/attachments`

## Route Ownership Matrix

| Current family | Canonical target family | Canonical owner | Status | Migration action | Policy notes |
|---|---|---|---|---|---|
| `/api/v1/files/*` | `/api/v1/files/*` | `workspace-core` | canonical | keep | files authority boundary; deny-by-default checks at owner |
| `/api/v1/git/*` | `/api/v1/git/*` | `workspace-core` | canonical | keep | git authority boundary; no duplicate owners |
| `/ws/pty` | `/ws/pty` (service-owned family) | `pty-service` | canonical | keep | PTY lifecycle + WS authority boundary |
| `/ws/claude-stream` | provisional `/api/v1/agent/normal/*` + stream family (Phase 1 finalize) | `agent-normal` | canonical | delegate | runtime/session orchestration only |
| `/api/sessions*` (boring-ui app) | provisional `/api/v1/agent/normal/*` session family | `agent-normal` | canonical | rewrite | keep side effects delegated to workspace-core/pty-service |
| `/api/approval/*` | `/api/approval/*` (current), Phase 1 contract freeze decides final prefixing | `workspace-core` boundary layer | canonical | keep | approval/policy lives with workspace authority boundary |
| `/api/capabilities` | `/api/capabilities` | runtime composition boundary | canonical | keep | capability gate source for `front` |
| `/api/config`, `/api/project` | `/api/config`, `/api/project` | runtime bootstrap boundary | canonical | keep | local runtime bootstrap; not control-plane contract |
| `/api/tree` | `/api/v1/files/list` | `workspace-core` | legacy | remove | rewrite frontend/tests to canonical files route |
| `/api/file` | `/api/v1/files/read|write|delete` | `workspace-core` | legacy | remove | split by method into canonical files endpoints |
| `/api/file/rename` | `/api/v1/files/rename` | `workspace-core` | legacy | remove | direct alias removal |
| `/api/file/move` | `/api/v1/files/move` | `workspace-core` | legacy | remove | direct alias removal |
| `/api/search` | `/api/v1/files/search` | `workspace-core` | legacy | remove | replace file search callsites |
| `/api/git/*` (legacy prefix) | `/api/v1/git/*` | `workspace-core` | legacy | remove | replace git callsites/tests/docs |
| `/api/attachments` | Phase 1 contract pack decision (likely agent-runtime family) | `agent-normal` (provisional) | legacy | rewrite | unresolved in-repo route; explicitly tracked risk |
| `/api/x/*` + `/ws/plugins` | `/api/x/*` + `/ws/plugins` | workspace plugin subsystem | canonical | keep | optional plugin boundary, runtime-scoped |
| `/api/v1/me` | `/api/v1/me` | control-plane | canonical | keep | frontend-callable canonical control-plane contract |
| `/api/v1/workspaces*` | `/api/v1/workspaces*` | control-plane | canonical | keep | workspace identity/runtime settings contract |
| `/auth/logout` | `/auth/logout` | control-plane | canonical | keep | session termination via control-plane |
| `/w/{workspace_id}/*` | `/w/{workspace_id}/*` | control-plane proxy boundary | canonical | keep | gateway policy + membership enforcement |
| `/api/sessions/*` (pi service) | provisional `/api/v1/agent/pi/*` (Phase 1 finalize) | `agent-pi` | canonical | rewrite | runtime-only PI API; delegated side effects |
| `/ws/browser/{sessionId}` (companion) | provisional `/api/v1/agent/companion/*` + stream family | `agent-companion` | canonical | rewrite | runtime-only companion API; delegated side effects |
| `/api/pi/*`, `/ws/pi-*` | none (explicitly non-existent in repo) | n/a | dead | remove | docs/scripts already describe as absent |
| `/ws/stream/{session}` | none (README stale reference) | n/a | dead | remove | stale documentation path, not implemented |

All known route families are explicitly classified as `canonical`, `legacy`, or `dead`.

## Route Status Summary

- canonical: service boundaries and control-plane contracts to preserve
- legacy: active callsites/docs still referencing pre-canonical families and aliases
- dead: route families referenced in stale docs or explicitly marked as absent

## Dependency-Aware Work Breakdown

Top-level phase chain encoded in beads:

1. `bd-3g1g.1` Phase 0 baseline and mapping
2. `bd-3g1g.2` Phase 1 contract freeze (blocked by `bd-3g1g.1`)
3. `bd-3g1g.3` Phase 2 shared transport boundary (blocked by `bd-3g1g.2`)
4. `bd-3g1g.4` Phase 2.5 auth/user-menu alignment (blocked by `bd-3g1g.3` + `bd-3g1g.3.4`)
5. `bd-3g1g.5` Phase 3 workspace-core and PTY ownership (blocked by `bd-3g1g.3`)
6. `bd-3g1g.6` Phase 4 agent delegation (blocked by `bd-3g1g.5`)
7. `bd-3g1g.7` Phase 5 cutover/verification/closeout (blocked by `bd-3g1g.4` + `bd-3g1g.6`)

Phase-0 internal chain is explicitly linearized:

1. `bd-3g1g.1.1` -> `bd-3g1g.1.2` -> `bd-3g1g.1.3` -> `bd-3g1g.1.4`

Critical path to migration closeout:

1. `bd-3g1g.1.1`
2. `bd-3g1g.1.2`
3. `bd-3g1g.1.3`
4. `bd-3g1g.1.4`
5. `bd-3g1g.2.1`
6. `bd-3g1g.2.2`
7. `bd-3g1g.2.3`
8. `bd-3g1g.3.1`
9. `bd-3g1g.3.2`
10. `bd-3g1g.3.3`
11. `bd-3g1g.3.4`
12. `bd-3g1g.5.1`
13. `bd-3g1g.5.2`
14. `bd-3g1g.5.4`
15. `bd-3g1g.6.1`
16. `bd-3g1g.6.2`
17. `bd-3g1g.6.3`
18. `bd-3g1g.6.4`
19. `bd-3g1g.6.5`
20. `bd-3g1g.7.1`
21. `bd-3g1g.7.5`
22. `bd-3g1g.7.2`
23. `bd-3g1g.7.3`
24. `bd-3g1g.7.4`

Note: `bd-3g1g.5.3` is intentionally off this strict blocking chain. It still remains required for full phase completion and documentation alignment, but it does not gate the minimal sequence above.

## Traceability Notes (Plan -> Beads)

| Plan section | Bead coverage |
|---|---|
| Phase 0 baseline and mapping | `bd-3g1g.1`, `bd-3g1g.1.1`, `bd-3g1g.1.2`, `bd-3g1g.1.3`, `bd-3g1g.1.4` |
| Phase 1 contract freeze | `bd-3g1g.2`, `bd-3g1g.2.1`, `bd-3g1g.2.2`, `bd-3g1g.2.3`, `bd-3g1g.2.4` |
| Phase 2 transport boundary | `bd-3g1g.3`, `bd-3g1g.3.1`, `bd-3g1g.3.2`, `bd-3g1g.3.3`, `bd-3g1g.3.4`, `bd-3g1g.3.5` |
| Phase 2.5 user-menu control-plane alignment | `bd-3g1g.4`, `bd-3g1g.4.1`, `bd-3g1g.4.2`, `bd-3g1g.4.3`, `bd-3g1g.4.4` |
| Phase 3 workspace-core + PTY ownership | `bd-3g1g.5`, `bd-3g1g.5.1`, `bd-3g1g.5.2`, `bd-3g1g.5.3`, `bd-3g1g.5.4`, `bd-3g1g.5.5` |
| Phase 4 agent delegation and policy | `bd-3g1g.6`, `bd-3g1g.6.1`, `bd-3g1g.6.2`, `bd-3g1g.6.3`, `bd-3g1g.6.4`, `bd-3g1g.6.5` |
| Phase 5 cutover and verification | `bd-3g1g.7`, `bd-3g1g.7.1`, `bd-3g1g.7.2`, `bd-3g1g.7.3`, `bd-3g1g.7.4`, `bd-3g1g.7.5` |

## Open Risks Captured in Baseline

1. `/api/attachments` is referenced by frontend but has no in-repo backend route in current scan.
2. Frontend still contains multiple legacy route families (`/api/tree`, `/api/file*`, `/api/search`, `/api/git/*`) that must be removed in Phase 2/5.
3. README and some docs still advertise legacy or dead route families and need cleanup in later doc beads.
