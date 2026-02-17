# Feature 4 Plan: Claude Web Chat Improvements Import Analysis (from `poc/opencode-web-chat`)

## Goal

Analyze the Claude web chat improvements done on `poc/opencode-web-chat` and identify what can be imported directly vs what should be adapted.

## Relevant Existing Code Studied

- Main current:
  - `src/front/components/chat/ClaudeStreamChat.jsx`
  - `src/front/panels/TerminalPanel.jsx`
  - `src/front/App.jsx`
- POC branch deltas:
  - `poc/opencode-web-chat:src/front/components/chat/ClaudeStreamChat.jsx`
  - `poc/opencode-web-chat:src/front/shared/normalizers/*`
  - `poc/opencode-web-chat:src/front/shared/renderers/*`
  - `poc/opencode-web-chat:src/front/providers/claude/adapter.jsx`
  - `poc/opencode-web-chat:src/front/hooks/useServiceConnection.js`
  - `poc/opencode-web-chat:src/front/utils/{apiFetch,wsAuth}.js`

## What Can Be Imported As-Is (Low Risk)

1. Shared renderers + normalizers
- `src/front/shared/renderers/*`
- `src/front/shared/normalizers/*`
- These are modular and mostly additive; minimal coupling to app shell.

2. Utility layer for fetch/ws token handling
- `src/front/utils/apiFetch.js`
- `src/front/utils/wsAuth.js`
- Improves hosted/direct-connect readiness without forcing full UI rewrite.

3. Claude provider adapter shell
- `src/front/providers/claude/adapter.jsx`
- Good extraction of session tabs and provider-level concerns from `TerminalPanel`.

## What Should Be Adapted (Medium Risk)

1. `ClaudeStreamChat.jsx` updates
- Keep improvements for shared renderer usage and mode-aware API calls.
- Review all API path changes carefully (POC introduces `/api/v1/*` assumptions).

2. `useServiceConnection` and capabilities coupling
- Import only if backend exposes `services` in `/api/capabilities`.
- Otherwise gate feature flags and keep fallback behavior.

3. Terminal provider switch
- Adapt `TerminalPanel` to provider registry incrementally, not big-bang.

## What Should Not Be Lifted Directly First (High Risk)

1. Full `App.jsx` hook refactor
- POC changes are very large and cross-cutting.
- Importing wholesale can destabilize layout persistence and panel behavior.

2. Broad style/global CSS changes
- Bring only provider/chat-scoped CSS first to avoid regressions.

## Recommended Import Order

1. Import shared renderers + tests.
2. Import Claude adapter + provider registry skeleton.
3. Patch ClaudeStreamChat to consume shared renderers and `apiFetch`.
4. Add service-connection integration only after backend capabilities contract is ready.
5. Defer large App hook refactor to separate epic.

## Acceptance Criteria

- Claude chat behavior remains parity with current main feature set.
- Tool rendering improves (consistent blocks, fewer provider-specific render bugs).
- No layout/panel regressions from initial import wave.
- Unit tests for normalizers/renderers pass in this repo.

