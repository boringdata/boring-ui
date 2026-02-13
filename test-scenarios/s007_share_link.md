# S-007: Share Link Create and Access

## Preconditions
- User authenticated with admin role on workspace.
- Workspace in `ready` state.
- Target file exists in workspace filesystem.

## Steps
1. Admin selects a file and creates a share link.
2. Control plane creates `file_share_links` row (service-role).
3. Admin receives the share URL with plaintext token.
4. External user accesses the share URL.
5. Control plane validates token hash, expiry, and revocation status.
6. Proxied file content returned.
7. Admin revokes the share link.
8. External user tries the same URL → denied.

## Expected Signals

### API
| Step | Endpoint | Status | Key Fields |
|---|---|---|---|
| 2 | `POST /api/v1/workspaces/{id}/shares` | 201 | `share_url`, `expires_at` |
| 5 | `GET /api/v1/shares/{token}` | 200 | File content |
| 7 | `PATCH /api/v1/workspaces/{id}/shares/{id}` | 200 | `revoked_at` set |
| 8 | `GET /api/v1/shares/{token}` | 410 | `share_expired` or `share_revoked` |

### UI
- Share dialog with generated URL and copy button.
- Expiry date display.
- Revoke button in share management.

## Evidence Artifacts
- API response: Share link creation.
- API response: Successful file access via share.
- API response: Revocation confirmation.
- API response: Denied access after revocation.

## Failure Modes
| Failure | Expected Behavior |
|---|---|
| Expired share link | 410 `share_expired` |
| Revoked share link | 410 `share_revoked` |
| Invalid token | 404 `share_not_found` |
| Path traversal in share path | Blocked by exact-path scope |
| Non-admin creates share | Blocked (service-role only INSERT) |
