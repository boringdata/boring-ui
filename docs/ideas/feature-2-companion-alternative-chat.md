# Feature 2 Plan: Integrate The Companion as Alternative Chat

## Goal

Provide The Companion (`https://github.com/The-Vibe-Company/companion`) as another selectable chat provider in boring-ui.

## Relevant Existing Code Studied

- POC branch implementation:
  - `poc/opencode-web-chat:src/back/boring_ui/api/modules/companion/provider.py`
  - `poc/opencode-web-chat:src/back/boring_ui/api/modules/companion/manager.py`
  - `poc/opencode-web-chat:src/back/boring_ui/api/modules/companion/router.py`
  - `poc/opencode-web-chat:src/front/providers/companion/adapter.jsx`
  - `poc/opencode-web-chat:src/front/providers/companion/config.js`
  - `poc/opencode-web-chat:src/front/hooks/useServiceConnection.js`
- Upstream companion snapshot inspected locally (`010e67c`):
  - `/tmp/companion-upstream-*/web/server/index.ts`
  - `/tmp/companion-upstream-*/web/server/routes.ts`

## Key Findings

- POC already has a working lifecycle-managed Companion provider in Python backend.
- POC frontend already mounts Companion UI via adapter and direct-connect config injection.
- Upstream Companion currently appears to have evolved (includes backend selection like Claude/Codex); this should be pinned to a known commit for reproducibility.

## Proposed Implementation

1. Backend Companion module (Phase 1)
- Port POC module set into main:
  - `src/back/boring_ui/api/modules/companion/*`
- Register `companion` router in `capabilities.py`.
- Compose manager startup/shutdown in `app.py` lifespan.

2. Service discovery and auth (Phase 2)
- Extend `/api/capabilities` to include `services.companion` URL/token metadata (POC pattern).
- Keep token issuance ephemeral and response non-cacheable (`Cache-Control: no-store`).
- Decide and enforce auth strategy:
  - forked Companion with auth middleware (POC approach), or
  - isolated network boundary only (less secure in multi-tenant hosted).

3. Frontend provider integration (Phase 3)
- Add companion provider adapter/config from POC:
  - `src/front/providers/companion/*`
- Register provider in `src/front/providers/index.js`.
- Select via `chat.provider = 'companion'`.

4. Dependency/vendor strategy (Phase 4)
- Add `vendor/companion` via pinned commit (or git submodule/subtree).
- Document Bun requirement and startup behavior.
- Add health/status checks in backend (`/api/companion/*`).

## Risks and Decisions

- Companion runtime dependency (`bun`) must be installed where API runs.
- Upstream changes may break our adapter; pinning is mandatory.
- Security model must be explicit before hosted rollout.

## Acceptance Criteria

- Companion can be started/stopped by backend manager.
- `chat.provider = 'companion'` renders Companion UI in terminal panel.
- Session creation/messages work end-to-end through direct connect.
- Capabilities endpoint returns usable companion connection metadata.

