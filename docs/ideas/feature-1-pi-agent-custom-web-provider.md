# Feature 1 Plan: PI Agent + Custom Web Frontend Provider

## Goal

Add PI Agent as an alternative chat provider in boring-ui, with its own web UI component, and make it selectable instead of the current Claude chat path.

## Relevant Existing Code Studied

- Current main branch chat entry:
  - `src/front/panels/TerminalPanel.jsx`
  - `src/front/components/chat/ClaudeStreamChat.jsx`
- Current backend composition:
  - `src/back/boring_ui/api/app.py`
  - `src/back/boring_ui/api/capabilities.py`
- Proven multi-provider pattern in POC branch:
  - `poc/opencode-web-chat:src/front/providers/registry.js`
  - `poc/opencode-web-chat:src/front/providers/index.js`
  - `poc/opencode-web-chat:src/front/panels/TerminalPanel.jsx`
  - `poc/opencode-web-chat:src/front/hooks/useServiceConnection.js`
  - `poc/opencode-web-chat:src/back/boring_ui/api/capabilities.py`

## Key Findings

- Main currently hardcodes Claude UI in `TerminalPanel`.
- POC branch already demonstrates provider-based chat switching (`claude`, `sandbox`, `inspector`, `companion`).
- No PI-specific implementation exists in current repo; PI should be integrated as a new provider using the same registry + adapter pattern.
- Upstream PI stack has a ready web component package:
  - `@mariozechner/pi-web-ui` (web components)
  - `@mariozechner/pi-agent-core` (agent runtime)
  - `@mariozechner/pi-ai` (provider/model abstraction)

## Proposed Implementation

1. Frontend provider architecture (Phase 1)
- Backport minimal provider registry from POC:
  - add `src/front/providers/registry.js`
  - add `src/front/providers/index.js`
- Refactor `src/front/panels/TerminalPanel.jsx` to:
  - load selected provider from config (`config.chat.provider`)
  - render the provider adapter component
  - preserve current collapse/review wiring

2. PI provider adapter (Phase 2)
- Add `src/front/providers/pi/index.js` and `src/front/providers/pi/adapter.jsx`.
- Wrap PI’s existing web component (`ChatPanel` / `AgentInterface`) inside adapter shell (terminal header + panel body).
- Keep PI-specific styling scoped (provider CSS + theme bridge) to avoid global bleed.
- Start with pinned package versions (no floating latest) for reproducible UI behavior.

3. Config and capability gating (Phase 3)
- Extend app config docs/defaults with `chat.provider: 'pi'`.
- If PI backend service is required, gate via `requiresCapabilities: ['pi']`.
- If PI can run client-side only, no backend capability flag is needed initially.

4. Backend direct-connect surface (optional, Phase 4)
- If PI requires a local service process:
  - add `modules/pi/{provider,manager,router}.py` (mirror `modules/companion`)
  - add service entry in capabilities response (`services.pi`) for URL/token delivery
  - use ephemeral token issuance pattern from POC capabilities/auth

## Risks and Decisions

- PI component contract unknown (props/events/session lifecycle). Adapter must isolate this.
- If PI requires backend auth tokens, token handling must stay in memory (no localStorage).
- Avoid large App refactor up front; start with targeted provider injection in `TerminalPanel`.
- Decide early whether PI runs:
  - directly in browser with provider API keys (fast, weaker key isolation), or
  - via control-plane/gateway-backed API (preferred for production multi-user).

## Acceptance Criteria

- `chat.provider = 'pi'` renders PI chat UI in terminal panel.
- `chat.provider = 'claude'` continues working unchanged.
- Missing PI capability (if required) shows clear fallback state, not runtime crash.
- Basic tests cover provider selection and fallback behavior.
