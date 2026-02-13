# S-003: Workspace Selection and Switch

## Preconditions
- User authenticated with active membership in 2+ workspaces.
- Both workspaces in `ready` state.
- Current workspace context set to workspace A.

## Steps
1. User opens workspace switcher UI.
2. Frontend calls `GET /api/v1/workspaces` → list of user's workspaces.
3. User selects workspace B.
4. Frontend calls `POST /api/v1/session/workspace` with workspace B ID.
5. Frontend navigates to `/w/{workspace_b_id}/app`.
6. Workspace B assets/files load via proxy.

## Expected Signals

### API
| Step | Endpoint | Status | Key Fields |
|---|---|---|---|
| 2 | `GET /api/v1/workspaces` | 200 | Array of workspaces with `id`, `name`, `runtime.state` |
| 4 | `POST /api/v1/session/workspace` | 200 | `workspace_id` updated |
| 6 | `GET /w/{id}/app` | 200 | Proxied workspace content |

### UI
- Workspace switcher shows all accessible workspaces.
- Selected workspace highlighted.
- Hard navigation to new workspace (full page transition).
- File tree reflects workspace B's filesystem.

## Evidence Artifacts
- API response: Workspace list.
- Screenshot: Workspace switcher with multiple entries.
- Screenshot: Workspace B loaded with correct file tree.

## Failure Modes
| Failure | Expected Behavior |
|---|---|
| User not member of workspace B | Workspace not in list (RLS filters it) |
| Workspace B runtime not ready | UI shows provisioning state, blocks navigation |
| app_context_mismatch (different app_id) | 400 `app_context_mismatch` |
