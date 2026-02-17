# S-007: Share Link Create and Access

## Preconditions
- User authenticated and inside a `ready` workspace.
- User has permission to create share links (workspace member).
- At least one file exists in the workspace to share.

## Steps
1. User selects a file in the file tree.
2. User initiates "Share" action (context menu or button).
3. App calls `POST /w/{workspace_id}/api/v1/shares` with `{ path, permissions }`.
4. Control plane creates share link and returns share token.
5. User copies the share link URL.
6. A different user (or unauthenticated browser) opens the share link.
7. App calls share access endpoint with the token.
8. Shared file content is displayed (read-only or read-write per permissions).
9. Original user revokes or expires the share link.

## Expected Signals

### API
| Step | Endpoint | Status | Key Fields |
|---|---|---|---|
| 3 | `POST /w/{id}/api/v1/shares` | 201 | `share_id`, `token`, `url`, `expires_at` |
| 7 | `GET /api/v1/shares/{token}` | 200 | File content or metadata |
| 9 | `DELETE /w/{id}/api/v1/shares/{share_id}` | 200 | Share revoked |

### UI
- Share dialog shows generated link with copy button.
- Shared view displays file content appropriately.
- Revoked share no longer accessible.

## Evidence Artifacts
- API response: share creation with token and URL.
- API response: share access returning file content.
- Screenshot: share dialog with generated link.
- Screenshot: shared file viewed by another user.
- API response: accessing expired/revoked share returns appropriate error.

## Failure Modes
| Failure | Expected Behavior |
|---|---|
| Unauthenticated share creation | 401 `no_credentials` |
| Non-member share creation | 403 `forbidden` |
| Expired share link | 410 `share_expired` |
| Unknown share token | 404 |
| Path traversal in share path | 400 `path_traversal` |
| Only token hash persisted | Raw token never stored server-side |
