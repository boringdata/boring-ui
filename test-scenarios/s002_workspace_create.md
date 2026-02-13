# S-002: Workspace Creation and Provisioning

## Preconditions
- User authenticated (session cookie valid).
- User has no existing workspaces.
- Modal sandbox provisioning endpoint available.
- Release artifact exists for `default_release_id`.

## Steps
1. App detects no workspace → shows onboarding/creation UI.
2. User enters workspace name and confirms.
3. Frontend calls `POST /api/v1/workspaces` with CSRF token.
4. Control plane creates workspace row, adds user as admin member.
5. Control plane creates provision job (state: `queued`).
6. Provision orchestrator progresses: `release_resolve` → `creating_sandbox` → `uploading_artifact` → `bootstrapping` → `health_check` → `ready`.
7. Frontend polls `GET /api/v1/workspaces/{id}/runtime` for status.
8. Runtime reaches `ready` → frontend navigates to workspace.

## Expected Signals

### API
| Step | Endpoint | Status | Key Fields |
|---|---|---|---|
| 3 | `POST /api/v1/workspaces` | 201 | `id`, `name`, `app_id` |
| 3 | (Side effect) | — | `workspace_members` row created with `role=admin`, `status=active` |
| 3 | (Side effect) | — | `workspace_runtime` row created with `state=provisioning` |
| 5 | (Side effect) | — | `workspace_provision_jobs` row with `state=queued` |
| 7 | `GET /api/v1/workspaces/{id}/runtime` | 200 | `state` progresses through lifecycle |
| 8 | `GET /api/v1/workspaces/{id}/runtime` | 200 | `state=ready`, `sandbox_name` populated |

### UI
- Onboarding screen with workspace name input.
- Provisioning progress indicator (state labels).
- Transition to workspace view on `ready`.

## Evidence Artifacts
- API response: Workspace creation (201).
- API responses: Runtime status progression.
- Screenshot: Provisioning progress indicator.
- Screenshot: Workspace ready state.
- Audit log: `workspace.created` event.

## Failure Modes
| Failure | Expected Behavior |
|---|---|
| Missing CSRF token | 403 `csrf_validation_failed` |
| Provision fails at `creating_sandbox` | Runtime `state=error`, `last_error_code` populated |
| Duplicate workspace name | (Allowed — names are not unique) |
| Unauthenticated request | 401 `no_credentials` |
