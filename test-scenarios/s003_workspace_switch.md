# S-003: Workspace Selection and Switch

## Preconditions
- User authenticated (session cookie active).
- User is a member of at least two workspaces, both in `ready` state.
- User is currently in workspace A (`/w/{workspace_a_id}/app`).

## Steps
1. User opens workspace switcher UI.
2. App calls `GET /api/v1/workspaces` → returns workspace list.
3. User selects workspace B from the list.
4. Browser navigates to `/w/{workspace_b_id}/app`.
5. App resolves workspace context from URL path.
6. App calls `GET /w/{workspace_b_id}/api/v1/files/` to load file tree.
7. Workspace B content loads in the panel layout.

## Expected Signals

### API
| Step | Endpoint | Status | Key Fields |
|---|---|---|---|
| 2 | `GET /api/v1/workspaces` | 200 | Array with workspace A and B |
| 5 | Routing resolves workspace context | — | `workspace_id` matches URL segment |
| 6 | `GET /w/{id}/api/v1/files/` | 200 | File tree for workspace B |

### UI
- Workspace switcher shows list of available workspaces.
- Current workspace highlighted/indicated.
- After switch, file tree and panels reflect workspace B content.
- No stale workspace A data visible.

## Evidence Artifacts
- Screenshot: workspace switcher showing multiple workspaces.
- Screenshot: workspace B loaded after switch.
- API response: `/api/v1/workspaces` showing both workspaces.
- API response: file tree call returning workspace B files.

## Failure Modes
| Failure | Expected Behavior |
|---|---|
| Workspace B in `error` state | UI shows error state, retry option |
| User not a member of workspace B | 403 `forbidden` |
| Workspace B does not exist | 404 |
| Workspace context mismatch (URL vs header) | 400 `workspace_context_mismatch` |
| Stale WebSocket from workspace A | Connection closed, new WS for workspace B |
