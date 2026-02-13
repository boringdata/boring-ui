# S-002: Workspace Creation and Provisioning

## Preconditions
- User authenticated (session cookie active, `/api/v1/me` returns 200).
- Control plane deployed and healthy.
- At least one release artifact available (app bundle published).
- No existing workspace for this test (or use unique workspace name).

## Steps
1. User navigates to workspace list or onboarding screen.
2. App calls `GET /api/v1/workspaces` → returns user's workspace list.
3. User clicks "Create workspace" and enters name.
4. App calls `POST /api/v1/workspaces` with `{ name, app_id }`.
5. Control plane returns `202 Accepted` with workspace metadata including `workspace_id` and `status: provisioning`.
6. App polls or receives update that provisioning is in progress.
7. Control plane provisions sandbox: resolves release → downloads bundle → verifies checksum → starts runtime.
8. Workspace transitions to `status: ready`.
9. User is redirected to `/w/{workspace_id}/app`.

## Expected Signals

### API
| Step | Endpoint | Status | Key Fields |
|---|---|---|---|
| 2 | `GET /api/v1/workspaces` | 200 | `workspaces[]` array |
| 4 | `POST /api/v1/workspaces` | 202 | `workspace_id`, `status: provisioning`, `sandbox_name` |
| 8 | `GET /api/v1/workspaces/{id}` | 200 | `status: ready`, `runtime_url` |

### UI
- Workspace list page loads (empty or with existing workspaces).
- Create form accepts workspace name.
- Provisioning spinner or progress indicator visible.
- After ready, workspace app loads.

## Evidence Artifacts
- API response: `POST /api/v1/workspaces` showing 202 with metadata.
- API response: workspace status polling showing `provisioning` → `ready`.
- Screenshot: workspace list before and after creation.
- `sandbox_name` matches deterministic format: `sbx-{app_id}-{workspace_id}-{env}`.

## Failure Modes
| Failure | Expected Behavior |
|---|---|
| Missing release artifact | `POST /api/v1/workspaces` → 503 `release_unavailable` |
| Checksum mismatch during provisioning | Workspace → `status: error`, error code in metadata |
| Provisioning timeout | Workspace → `status: error` with `provisioning_timeout` code |
| Duplicate workspace name | 409 or validation error (depends on uniqueness constraint) |
| Unauthenticated call | 401 `no_credentials` |
| Concurrent create calls | Single-active-job invariant preserved |
