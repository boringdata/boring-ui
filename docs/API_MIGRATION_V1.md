# API Contract (Canonical v1)

## Status

Migration is complete for privileged browser operations.

- Canonical browser contract: `/api/v1/*`
- Canonical private workspace contract: `/internal/v1/*`
- Hosted mode does not expose legacy privileged compatibility routes.

## Canonical Browser Endpoints

### Files

- `GET /api/v1/files/list?path=.`
- `GET /api/v1/files/read?path=<path>`
- `POST /api/v1/files/write`
- `DELETE /api/v1/files/delete?path=<path>`
- `POST /api/v1/files/rename`
- `POST /api/v1/files/move`
- `GET /api/v1/files/search?q=<pattern>&path=.`

### Git

- `GET /api/v1/git/status`
- `GET /api/v1/git/diff?path=<path>`
- `GET /api/v1/git/show?path=<path>`

### Exec

- `POST /api/v1/exec/run`

## Request/Response Notes

- Write/rename/move/exec use JSON request bodies.
- File list uses `files` with `type: "file" | "dir"`.
- Read/show responses include metadata fields used by current frontend contracts.

## Auth Semantics

- `local` mode: no OIDC required for browser routes.
- `hosted` mode: OIDC middleware applies to non-health routes; privileged operations are served through canonical `/api/v1/*` when capability signing is configured.

## Non-Goals

- No deprecation-header workflow for legacy privileged routes in hosted runtime.
- No browser contract based on `/api/tree`, `/api/file`, `/api/search`, or `/api/v1/sandbox/proxy/*`.
