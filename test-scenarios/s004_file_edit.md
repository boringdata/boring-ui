# S-004: File Editing Workflow

## Preconditions
- User authenticated, workspace selected and in `ready` state.
- Workspace has a file tree with at least one editable file.
- Workspace runtime sandbox is running and proxied.

## Steps
1. Frontend loads file tree via `GET /w/{id}/api/v1/files`.
2. User clicks a file in the tree.
3. Frontend loads file content via `GET /w/{id}/api/v1/files?path=<path>`.
4. User edits the file in the editor panel.
5. User saves → `PUT /w/{id}/api/v1/files` with updated content.
6. File tree reflects any name/path changes.
7. Git panel shows the file as modified (`GET /w/{id}/api/v1/git/status`).

## Expected Signals

### API
| Step | Endpoint | Status | Key Fields |
|---|---|---|---|
| 1 | `GET /w/{id}/api/v1/files` | 200 | File tree JSON |
| 3 | `GET /w/{id}/api/v1/files?path=...` | 200 | File content |
| 5 | `PUT /w/{id}/api/v1/files` | 200 | Updated file confirmation |
| 7 | `GET /w/{id}/api/v1/git/status` | 200 | Modified files list |

### UI
- File tree with expandable directories.
- Editor panel with syntax highlighting.
- Save indicator (success/failure).
- Git changes panel shows modified file.

## Evidence Artifacts
- Screenshot: File tree loaded.
- Screenshot: File open in editor.
- Screenshot: Git status showing modification.
- API response: File content before and after edit.

## Failure Modes
| Failure | Expected Behavior |
|---|---|
| Path traversal attempt | 400 (blocked by path validation) |
| File not found | 404 |
| Workspace runtime down | 502/504 (proxy timeout) |
| CSRF token missing on PUT | 403 `csrf_validation_failed` |
