# S-004: File Editing Workflow

## Preconditions
- User authenticated and inside a `ready` workspace (`/w/{workspace_id}/app`).
- Workspace has at least one existing file (e.g., `README.md`).
- File tree panel visible.

## Steps
1. User sees file tree panel with workspace files.
2. App calls `GET /w/{workspace_id}/api/v1/files/` → file tree loaded.
3. User clicks a file (`README.md`) in the file tree.
4. App calls `GET /w/{workspace_id}/api/v1/files/README.md` → file content loaded.
5. Editor panel opens with file content.
6. User edits file content.
7. User saves the file.
8. App calls `PUT /w/{workspace_id}/api/v1/files/README.md` with new content.
9. File saved confirmation shown.
10. User creates a new file via file tree context menu.
11. App calls `POST /w/{workspace_id}/api/v1/files/new-file.txt` with content.
12. New file appears in file tree.

## Expected Signals

### API
| Step | Endpoint | Status | Key Fields |
|---|---|---|---|
| 2 | `GET /w/{id}/api/v1/files/` | 200 | File tree with names, sizes |
| 4 | `GET /w/{id}/api/v1/files/README.md` | 200 | File content |
| 8 | `PUT /w/{id}/api/v1/files/README.md` | 200 | Success confirmation |
| 11 | `POST /w/{id}/api/v1/files/new-file.txt` | 201 | Created file metadata |

### UI
- File tree shows hierarchical file listing.
- Editor displays file content with syntax highlighting.
- Save indicator (dirty/clean state) visible.
- New file appears in tree after creation.

## Evidence Artifacts
- Screenshot: file tree with files listed.
- Screenshot: editor panel with file content open.
- API response: file read and write responses.
- Screenshot: new file visible in file tree after creation.

## Failure Modes
| Failure | Expected Behavior |
|---|---|
| File not found | 404 `file_not_found` |
| Path traversal attempt (`../etc/passwd`) | 400 `path_traversal` |
| File too large for editor | Graceful handling (download or truncation) |
| Write to read-only file | 403 or appropriate error |
| Non-member access | 403 `forbidden` |
| Concurrent edit conflict | Last-write-wins or conflict resolution |
