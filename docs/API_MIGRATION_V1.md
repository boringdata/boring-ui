# API v1 Migration Guide (bd-1pwb.6.3)

## Overview

Boring UI is migrating from legacy `/api/*` endpoints to canonical `/api/v1/*` endpoints.
Legacy endpoints continue to work but return deprecation headers signaling the transition.

## Timeline

| Phase | Date | Action |
|-------|------|--------|
| Deprecation headers added | 2026-02-12 | Legacy routes return `Deprecation: true` |
| Migration window | 2026-02-12 — 2026-08-01 | Both legacy and v1 routes operational |
| Sunset | 2026-08-01 | Legacy routes may be removed |

## Route Mapping

### File Operations

| Legacy | Canonical v1 | Method | Notes |
|--------|-------------|--------|-------|
| `GET /api/tree?path=.` | `GET /api/v1/files/list?path=.` | GET | Response shape differs (see below) |
| `GET /api/file?path=x` | `GET /api/v1/files/read?path=x` | GET | Same content, v1 adds `size` field |
| `PUT /api/file?path=x` | `POST /api/v1/files/write` | POST | v1 uses JSON body `{path, content}` |
| `GET /api/search?q=*.py` | — | GET | No v1 equivalent yet |
| `DELETE /api/file?path=x` | — | DELETE | No v1 equivalent yet |
| `POST /api/file/rename` | — | POST | No v1 equivalent yet |
| `POST /api/file/move` | — | POST | No v1 equivalent yet |

### Git Operations

| Legacy | Canonical v1 | Method | Notes |
|--------|-------------|--------|-------|
| `GET /api/git/status` | `GET /api/v1/git/status` | GET | Same shape: `{is_repo, files}` |
| `GET /api/git/diff?path=x` | `GET /api/v1/git/diff?path=x` | GET | Same shape: `{diff, path}` |
| `GET /api/git/show?path=x` | `GET /api/v1/git/show?path=x` | GET | v1 adds `is_new` field |

### Exec Operations (HOSTED mode only)

| Legacy | Canonical v1 | Method | Notes |
|--------|-------------|--------|-------|
| — | `POST /api/v1/exec/run` | POST | New in v1. JSON body `{command, timeout_seconds}` |

## Response Shape Changes

### List Files

**Legacy** (`GET /api/tree`):
```json
{
  "entries": [
    {"name": "app.py", "path": "app.py", "is_dir": false, "size": 1024}
  ],
  "path": "."
}
```

**v1** (`GET /api/v1/files/list`):
```json
{
  "files": [
    {"name": "app.py", "type": "file", "size": 1024}
  ],
  "path": "."
}
```

Key differences:
- `entries` → `files` (field rename)
- `is_dir` → `type: "file" | "dir"` (boolean → string enum)
- `path` field removed from each entry (was redundant with `name`)

### Read File

**Legacy** (`GET /api/file`):
```json
{"content": "...", "path": "app.py"}
```

**v1** (`GET /api/v1/files/read`):
```json
{"content": "...", "path": "app.py", "size": 1024}
```

v1 adds `size` field.

### Write File

**Legacy** (`PUT /api/file?path=x`, body: `{"content": "..."}`):
```json
{"success": true, "path": "app.py"}
```

**v1** (`POST /api/v1/files/write`, body: `{"path": "x", "content": "..."}`):
```json
{"path": "app.py", "size": 1024, "written": true}
```

Key differences:
- Method changed from PUT to POST
- Path moved from query param to JSON body
- Response adds `size`, renames `success` → `written`

### Git Show

**Legacy** (`GET /api/git/show`):
```json
{"content": "...", "path": "app.py"}
```

**v1** (`GET /api/v1/git/show`):
```json
{"content": "...", "path": "app.py", "is_new": false}
```

v1 adds `is_new` field (true when file is not tracked in HEAD).

## Deprecation Headers

Legacy responses include these headers:

```
Deprecation: true
Sunset: 2026-08-01T00:00:00Z
Link: </api/v1/files/list>; rel="successor-version"
```

Clients can detect deprecation by checking for the `Deprecation` header.

## Auth Behavior

| Mode | Legacy Routes | v1 Routes |
|------|--------------|-----------|
| LOCAL | No auth required | No auth required |
| HOSTED | OIDC JWT required | OIDC JWT required |

Both route sets have identical auth requirements per mode.

## Migration Checklist

For frontend migration:

- [ ] Update `GET /api/tree` → `GET /api/v1/files/list` (adapt `entries` → `files`)
- [ ] Update `GET /api/file` → `GET /api/v1/files/read`
- [ ] Update `PUT /api/file` → `POST /api/v1/files/write` (move path to body)
- [ ] Update `GET /api/git/status` → `GET /api/v1/git/status`
- [ ] Update `GET /api/git/diff` → `GET /api/v1/git/diff`
- [ ] Update `GET /api/git/show` → `GET /api/v1/git/show`
- [ ] Handle `is_new` field in git show responses
- [ ] Remove any `/api/search` usage (use files/list with client-side filtering or wait for v1 search)
