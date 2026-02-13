# S-006: Provisioning Failure and Retry

## Preconditions
- User authenticated.
- At least one scenario where provisioning can fail (e.g., release artifact missing, checksum mismatch, or runtime timeout).
- User has permission to create workspaces.

## Steps
1. User creates a new workspace via `POST /api/v1/workspaces`.
2. Control plane returns 202 with `status: provisioning`.
3. Provisioning encounters a failure (timeout, checksum mismatch, or artifact unavailable).
4. Workspace transitions to `status: error` with an actionable error code.
5. User sees error state in the UI with a retry option.
6. User clicks retry.
7. App calls `POST /api/v1/workspaces/{id}/retry` (or equivalent retry endpoint).
8. New provisioning attempt starts → `status: provisioning`.
9. Provisioning succeeds → `status: ready`.

## Expected Signals

### API
| Step | Endpoint | Status | Key Fields |
|---|---|---|---|
| 1 | `POST /api/v1/workspaces` | 202 | `workspace_id`, `status: provisioning` |
| 4 | `GET /api/v1/workspaces/{id}` | 200 | `status: error`, `error_code`, `error_detail` |
| 7 | `POST /api/v1/workspaces/{id}/retry` | 202 | New provisioning attempt started |
| 9 | `GET /api/v1/workspaces/{id}` | 200 | `status: ready` |

### UI
- Provisioning progress indicator initially shown.
- Error state displayed with actionable error message.
- Retry button visible and clickable.
- After retry, provisioning progress shown again.
- Successful provisioning leads to workspace ready state.

## Evidence Artifacts
- API response: workspace in `error` state with error code.
- API response: retry call returning 202.
- API response: workspace transitioning to `ready` after retry.
- Screenshot: error state UI with retry button.
- Screenshot: workspace ready after successful retry.

## Failure Modes
| Failure | Expected Behavior |
|---|---|
| Multiple rapid retry clicks | Single-active-job invariant; extra retries rejected or queued |
| Retry on workspace that is already provisioning | 409 or appropriate conflict response |
| Persistent failure after retry | Workspace stays in `error` with updated error details |
| Missing release on retry (still unavailable) | 503 `release_unavailable` again |
