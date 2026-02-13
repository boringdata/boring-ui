# S-006: Provisioning Failure and Retry

## Preconditions
- User authenticated with admin role on workspace.
- Workspace in `error` state after failed provisioning.
- `workspace_provision_jobs` has a completed `error` job.

## Steps
1. Frontend loads workspace runtime status → `state=error`.
2. UI displays error details (`last_error_code`, `last_error_detail`).
3. User clicks retry button.
4. Frontend calls `POST /api/v1/workspaces/{id}/retry` with CSRF token.
5. New provision job created (state: `queued`).
6. Provisioning progresses through lifecycle states.
7. Runtime reaches `ready` → workspace usable.

## Expected Signals

### API
| Step | Endpoint | Status | Key Fields |
|---|---|---|---|
| 1 | `GET /api/v1/workspaces/{id}/runtime` | 200 | `state=error`, `last_error_code` |
| 4 | `POST /api/v1/workspaces/{id}/retry` | 200 | New job ID |
| 4 | (Side effect) | — | Previous job `state=error`, new job `state=queued` |
| 6 | `GET /api/v1/workspaces/{id}/runtime` | 200 | `state=provisioning` |
| 7 | `GET /api/v1/workspaces/{id}/runtime` | 200 | `state=ready` |

### UI
- Error state with clear error message and retry button.
- Provisioning progress after retry.
- Transition to ready state.

## Evidence Artifacts
- Screenshot: Error state with retry button.
- API response: Error runtime status.
- API response: Retry response with new job.
- Screenshot: Successful recovery to ready state.

## Failure Modes
| Failure | Expected Behavior |
|---|---|
| Retry also fails | `state=error` with new `last_error_code`, `attempt` incremented |
| Active job already exists | Retry blocked by `ux_workspace_jobs_active` unique index |
| Non-admin tries retry | 403 (insufficient permissions) |
