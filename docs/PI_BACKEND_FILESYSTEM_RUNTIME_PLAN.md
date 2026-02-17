# PI Backend Filesystem Runtime Plan

## Goal
Move PI mode from browser-executed runtime to backend-executed runtime so PI runs in server workspace/filesystem context and uses server-managed credentials.

## Current State
- PI agent is instantiated in frontend (`src/front/providers/pi/nativeAdapter.jsx`).
- Model/provider calls happen from browser context.
- PI key flow is browser-side.
- Backend exposes PI capability flag, but no dedicated PI runtime transport (`/api/pi/*`, `/ws/pi-*`).

## Target State
- PI runs in a dedicated Node service in workspace context (`cwd=workspace_root`).
- Frontend PI panel is transport/UI only.
- Server owns provider keys (Vault/env), browser never handles secret keys.

## Delivery Plan

### 1. Dedicated PI Service Contract (Node)
- Add REST endpoints:
  - `POST /api/sessions/create`
  - `GET /api/sessions`
  - `GET /api/sessions/{id}/history`
  - `POST /api/sessions/{id}/stop`
  - `POST /api/sessions/{id}/stream` (SSE)
- Define stream event protocol:
  - `session`
  - `delta`
  - `done`
  - `error`

### 2. Runtime Implementation (Node + PI packages)
- Use `@mariozechner/pi-agent-core` for agent lifecycle.
- Use `@mariozechner/pi-ai` providers/models directly server-side.
- Implement in-memory session manager with lifecycle tracking and cleanup.
- Execute in workspace directory and keep agent state server-side.
- Add idle timeout, per-session timeout, and max concurrent sessions.

### 3. Security and Credential Handling
- Use server-only PI provider credentials from env/Vault injection.
- Remove browser API key dependency in backend PI mode.
- Redact secrets in logs and errors.
- Enforce workspace/path guardrails for all PI tool/file operations.

### 4. Frontend PI Adapter Refactor
- Keep current right-rail PI UI and session toolbar.
- Replace browser PI runtime calls with dedicated PI service session + stream calls.
- Keep composer pinned at bottom and message area scrollable.
- Remove browser key prompt path when backend PI mode is active.

### 5. Integration and Config
- PI service process/env:
  - `PI_SERVICE_HOST`
  - `PI_SERVICE_PORT`
  - `PI_SERVICE_MODEL`
  - `PI_SERVICE_MAX_SESSIONS`
- Extend `/api/capabilities` PI service payload:
  - `features.pi = true`
  - `services.pi = { mode: "backend", url: "http://<pi-service-host>:<port>" }`
- Frontend config fallback:
  - `VITE_PI_SERVICE_URL`
- Keep browser mode only as temporary fallback during migration.

### 6. Testing
- Backend unit tests:
  - session lifecycle
  - stop idempotency
  - missing key behavior
  - timeout/cleanup
- Backend integration tests:
  - create session -> send prompt -> receive streamed response -> stop
- Frontend/Playwright:
  - PI mode sends/receives in right rail
  - no browser key prompt in backend mode
  - no UI stalls and composer remains bottom-pinned
- Regression:
  - Companion mode and native agent mode still functional.

### 7. Evidence and Acceptance
- Showboat evidence for:
  - PI backend chat response in `?agent_mode=pi`
  - session create/switch/stop behavior
  - right-rail layout + bottom composer behavior
- Rodney screenshots for expanded and collapsed PI rail.
- `showboat verify` must pass before closure.

## Milestones

### Milestone A (MVP)
- Dedicated Node PI session/stream endpoints live.
- Frontend PI uses dedicated service transport.
- End-to-end PI response working with server key.

### Milestone B (Hardening)
- Resume robustness, limits, cleanup, and better error recovery.
- Hosted-mode auth/capability enforcement aligned.
- Optional FastAPI edge proxy for unified policy/audit.
- Remove or minimize browser fallback surface.

## Definition of Done
- PI mode runs server-side (not browser-side) by default.
- Vault/env credential is used only on backend.
- PI panel is functional in right rail with bottom composer.
- Companion/native modes remain functional.
- Tests + evidence + review pass.
