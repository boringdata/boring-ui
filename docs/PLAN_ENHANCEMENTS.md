# Plan Enhancements (Additional Proposals)

## Summary
This file contains the additional proposed plan upgrades not merged into `docs/PLAN.md` yet. Each proposal includes rationale and a git-diff style change against the current plan.

## Proposal 1: Feature Bundles
**Why**
Feature bundles unify panes, routes, and capabilities into a single composable unit. This prevents partial integrations, reduces drift between front and back, and makes extension development safer and faster.

**Diff**
```diff
diff --git a/docs/PLAN.md b/docs/PLAN.md
@@
 ## Composability Enhancements (Panes + Routes)
 - Add optional pane metadata for backend requirements.
 - Metadata: `requiresFeatures: ['files', 'git', 'pty', 'chat_claude_code']`.
 - Metadata: `requiresRouters: ['files', 'git', 'pty', 'chat-claude-code']`.
 - Use `/api/capabilities` to enable/disable panes at runtime (hide panes when backend lacks required features).
 - Keep a small `modules/` convention for adding new features.
 - Backend convention: `src/back/boring_ui/api/modules/<feature>/router.py`.
 - Frontend panes: `src/front/panels/<Feature>Panel.jsx`.
 - Frontend reusable UI: `src/front/components/<Feature>/...`.
 - Optional: `src/front/registry/panes.js` exposes a single `registerPane()` per feature.
+## Feature Bundles
+- Define a feature bundle per capability to unify panes, routes, and config.
+- Frontend bundle path: `src/front/features/<feature>/index.js`.
+- Frontend bundle exports: `registerPanes(registry)` and `requiredCapabilities()`.
+- Backend bundle path: `src/back/boring_ui/api/modules/<feature>/__init__.py`.
+- Backend bundle exports: `register(registry)` and `capabilities()`.
+- App loads bundles to auto-register panes and routers in one place.
```

## Proposal 2: API Versioning and Error Envelope
**Why**
Stable API versions and a consistent error shape make clients more reliable, reduce edge-case handling, and enable safer changes over time.

**Diff**
```diff
diff --git a/docs/PLAN.md b/docs/PLAN.md
@@
 **Capabilities Contract**
-- `GET /api/capabilities` returns `{ version, features, routers }`.
+- `GET /api/capabilities` returns `{ apiVersion, schemaVersion, build, features, routers }`.
  Features include: `files`, `git`, `pty`, `chat_claude_code`, `approval`.
  For backward compatibility, keep `stream` as an alias to `chat_claude_code` until all clients migrate.
+**Error Contract**
+- All HTTP errors return `{ error: { code, message, details, requestId } }`.
+- All responses include `x-request-id` for tracing.
```

## Proposal 3: Scalable Files API
**Why**
Large repos will overwhelm `tree` and `search`. Pagination, depth limits, and caching avoid timeouts and reduce bandwidth.

**Diff**
```diff
diff --git a/docs/PLAN.md b/docs/PLAN.md
@@
 **Files API (modules/files)**
-- `GET /api/v1/files/list?path=.` list directory entries.
+- `GET /api/v1/files/list?path=.` list directory entries.
+- `GET /api/v1/files/list?path=.&depth=1&limit=500&cursor=<id>` for pagination.
+- `GET /api/v1/files/list?includeHidden=false&respectGitignore=true` for safe defaults.
+- Response includes `nextCursor`, `hasMore`, and `stats` for large dirs.
 - `GET /api/v1/files/read?path=...` read file content.
+- `HEAD /api/v1/files/read?path=...` return metadata only.
+- `GET /api/v1/files/read?path=...` returns `etag` and `lastModified`.
+- Support `If-None-Match` to return `304` when unchanged.
 - `PUT /api/v1/files/write?path=...` write file content with `{ content }`.
 - `DELETE /api/v1/files/delete?path=...` delete file.
 - `POST /api/v1/files/rename` with `{ old_path, new_path }`.
 - `POST /api/v1/files/move` with `{ src_path, dest_dir }`.
-- `GET /api/v1/files/search?q=pattern&path=.` glob-style filename search.
+- `GET /api/v1/files/search?q=pattern&path=.` glob-style filename search.
+- `GET /api/v1/files/search?mode=content&limit=200&cursor=<id>` for content search.
+- `POST /api/v1/files/batch` to read multiple files in one request.
```

## Proposal 4: Unified Events Channel
**Why**
Polling for file or git changes is costly and slow. A WebSocket event stream reduces load and improves UI responsiveness.

**Diff**
```diff
diff --git a/docs/PLAN.md b/docs/PLAN.md
@@
 **PTY API (modules/pty)**
 - `WS /ws/pty?session_id=<id>&provider=<name>` for terminal sessions.
 - Messages include `{ type: "input", data: "..." }` and `{ type: "resize", rows, cols }`.
+**Events API (modules/events)**
+- `WS /ws/events` for server-pushed updates.
+- Event types: `files.changed`, `git.status`, `chat.session`, `approval.updated`.
+- Frontend switches from polling to event-driven updates when available.
```

## Proposal 5: Approval Integration for Destructive Actions
**Why**
This leverages the existing approval workflow to prevent accidental destructive changes and aligns governance across chat and file operations.

**Diff**
```diff
diff --git a/docs/PLAN.md b/docs/PLAN.md
@@
 **Approval API (modules/chat_claude_code/approval.py)**
 - `POST /api/approval/request` create approval.
 - `GET /api/approval/pending` list pending approvals.
 - `POST /api/approval/decision` submit approve/deny.
 - `GET /api/approval/status/{request_id}` status.
 - `DELETE /api/approval/{request_id}` delete.
+**Approval Integration**
+- Optionally require approvals for destructive file actions and git operations.
+- Use config flags to enable approval gating per feature.
```
