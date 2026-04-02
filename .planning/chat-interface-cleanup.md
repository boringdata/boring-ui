# Chat Interface Cleanup: Unified Agent Transport

**Status:** Phase 1-2 DONE, Phase 3 open — 2026-04-02
**Builds on:** `pi-migration-phase-ab.md` (completed)
**Reviewed by:** Codex (o3) — feedback incorporated

---

## Problem

The chat interface has 3 separate rendering paths, each with its own streaming logic, message format, and session management:

```
BEFORE (3 paths, 3 UIs):

Chat layout (layouts/chat/)
  └─ useChatTransport(capabilities)       ← capability sniffing
       ├─ PiAgentCoreTransport             ← browser agent
       └─ DefaultChatTransport             ← server agent

IDE layout (shared/panels/)
  └─ AgentPanel (3-way conditional)
       ├─ PiNativeAdapter (857 lines)      ← pi-web-ui ChatPanel
       ├─ PiBackendAdapter (516 lines)     ← custom SSE streaming
       └─ AiChat (299 lines)              ← own useChat + DefaultChatTransport
```

---

## Architecture (target)

```
  3 URL params (dev mode):
    ?layout=chat|ide           — which layout to render
    ?agent_mode=frontend|backend   — where the agent runs
    ?chat=pi|vercel-sdk        — which chat interface

  config.agents.mode = 'frontend' | 'backend'

  useAgentTransport()                        ← shared/providers/agent/
    ├─ 'frontend' → PiAgentCoreTransport     ← browser tools + session API keys
    └─ 'backend'  → DefaultChatTransport     ← /api/v1/agent/chat + workspace scope
                         │
                    useChat({ transport })    ← @ai-sdk/react
                         │
                    ChatStage / ChatMessage / ChatComposer
                         │
              ┌──────────┴──────────┐
              │                     │
         Chat layout           IDE layout
      (layouts/chat/)    (shared/panels/AgentPanel)
```

---

## Frontend Structure (post-refactor)

```
src/front/
  App.jsx                                   ← layout routing, dev banner
  layouts/
    chat/
      ChatCenteredWorkspace.jsx             ← orchestrator (uses useAgentTransport)
      ChatStage.jsx                         ← message list + composer container
      NavRail.jsx                           ← left icon strip
      BrowseDrawer.jsx                      ← session history drawer
      SurfaceShell.jsx                      ← right workbench
      SurfaceDockview.jsx                   ← DockView inside Surface
      useChatCenteredShell.js               ← ?layout= routing
      layout.css                            ← layout styles + API key prompt
      components/
        ChatComposer.jsx                    ← input + model selector + thinking toggle
        ApiKeyPrompt.jsx                    ← inline key entry (frontend mode)
      hooks/
        useSessionState.js                  ← session store (localStorage)
        useArtifactController.js            ← Surface artifact lifecycle
        useToolBridge.js                    ← window bridge for PI tools
        useShellPersistence.js              ← layout state persistence
        useShellStatePublisher.js           ← state → backend sync
  shared/
    providers/
      agent/
        useAgentTransport.js                ← config-driven transport hook
        index.js                            ← barrel export
      pi/
        piAgentCoreTransport.js             ← browser agent bridge
        defaultTools.js                     ← tool definitions
        agentConfig.js                      ← child app tool extension
        envApiKeys.browser.js               ← API key resolution from env
        useChatTransport.js                 ← OLD (replaced by useAgentTransport)
        nativeAdapter.jsx                   ← OLD (857 lines, IDE layout only)
        backendAdapter.jsx                  ← OLD (516 lines, IDE layout only)
      data/
        DataContext.js                      ← useDataProvider hook
    panels/
      AgentPanel.jsx                        ← IDE layout agent routing
    components/
      chat/
        ChatMessage.jsx                     ← message part renderer (shared)
        AiChat.jsx                          ← OLD (299 lines, IDE layout only)
        chat-stage.css                      ← chat styles (thinking + model selector)
    config/
      appConfig.js                          ← agents.mode config
    design-system/
      base.css                              ← dev banner styles
```

---

## URL Params (dev mode)

| Param | Values | Purpose |
|-------|--------|---------|
| `layout` | `chat` \| `ide` | Which layout to render |
| `agent_mode` | `frontend` \| `backend` | Where the agent runs |
| `chat` | `pi` \| `vercel-sdk` | Which chat interface (future) |

```
# All valid combinations:
?layout=chat&agent_mode=frontend              ← chat layout, browser agent
?layout=chat&agent_mode=backend               ← chat layout, server agent
?layout=ide&agent_mode=frontend               ← IDE layout, browser agent
?layout=ide&agent_mode=backend                ← IDE layout, server agent

# With chat interface selection:
?layout=chat&agent_mode=frontend&chat=pi
?layout=chat&agent_mode=backend&chat=vercel-sdk
```

Dev banner shows: `layout:chat · agent:frontend · chat:pi`

## Config

```javascript
// shared/config/appConfig.js
agents: {
  mode: 'frontend',   // 'frontend' | 'backend'
}
```

---

## Phase 1: Transport layer + chat layout — DONE

**Created:**
| File | Purpose |
|------|---------|
| `shared/providers/agent/useAgentTransport.js` | Config-driven transport, workspace scoping, session API keys, model/thinking controls |
| `shared/providers/agent/index.js` | Barrel export |

**Modified:**
| File | Change |
|------|--------|
| `layouts/chat/ChatCenteredWorkspace.jsx` | `useAgentTransport()` replaces `useChatTransport(capabilities)`, removed CapabilitiesContext |
| `layouts/chat/__tests__/ChatCenteredWorkspace.test.jsx` | Updated mock path |
| `App.jsx` | Dev mode banner with layout/agent/chat params |
| `shared/design-system/base.css` | `.dev-mode-banner` styles |

**Key decisions:**
- `resolveAgentMode()` checks `?agent_mode=` URL param first, then `config.agents.mode`
- Frontend transport: ref-stable (preserves Agent state), tools updated via `updateTools()`
- Backend transport: `useMemo` keyed on `workspaceId` (recreates on workspace change)
- `messages: sessionMessages` preserved in useChat (Codex review catch)
- `resolveApiKey()` checks env vars first, then session key store

---

## Phase 2: Feature parity — DONE

**Created:**
| File | Purpose |
|------|---------|
| `layouts/chat/components/ApiKeyPrompt.jsx` | Inline API key entry, stores via `setSessionApiKey()` |

**Modified:**
| File | Change |
|------|--------|
| `shared/providers/pi/piAgentCoreTransport.js` | `setThinkingLevel()`, `setModel()`, `getAvailableModels()`, `MODEL_CANDIDATES`, `THINKING_LEVELS` |
| `layouts/chat/components/ChatComposer.jsx` | Thinking toggle (Brain icon, cycles off→low→high), model selector dropdown |
| `layouts/chat/ChatStage.jsx` | Props threading: thinkingLevel, model, agentMode |
| `layouts/chat/ChatCenteredWorkspace.jsx` | Wires all controls from useAgentTransport → ChatStage → ChatComposer |
| `shared/components/chat/chat-stage.css` | `.vc-thinking-toggle`, `.vc-model-selector`, `.vc-model-menu` styles |
| `layouts/chat/layout.css` | `.vc-apikey-prompt` styles |

**Bug fixes (found during testing):**
| Fix | File | Details |
|-----|------|---------|
| open_file bridge conflict | `shared/hooks/usePanelActions.js` | IDE layout's bridge was overwriting chat layout's bridge; added guard via `SURFACE_OPEN_FILE_BRIDGE` check |
| Orphaned tool_use blocks | `server/http/aiSdkRoutes.ts` | `stripOrphanedToolCalls()` removes tool-call parts without matching tool-result before sending to Anthropic API |
| Deprecated model | `server/http/aiSdkRoutes.ts` | `claude-3-5-haiku-latest` → `claude-haiku-4-5-20251001` |

**Skipped:**
- XML tool normalization — edge case, deferred
- Session persistence bridge (localStorage → IndexedDB) — needs investigation, not blocking

---

## Phase 3: Wire IDE layout + deprecate adapters — OPEN

**Prerequisite:** Validate Phases 1-2 in production first.

**Modify:**
| File | Change |
|------|--------|
| `shared/panels/AgentPanel.jsx` | Replace 3-way routing with `useChat` + `useAgentTransport` + `ChatStage` |

**Session controller (from Codex review):**
AgentPanel passes `panelId`, `sessionBootstrap`, `piInitialSessionId` into panel-scoped session machinery. Rewrite needs either:
- `useAgentSessionController` hook covering these flows, OR
- Simplified session logic if DockView panel splitting is no longer needed

**Deprecate (mark `@deprecated`, do not delete):**
| File | Lines | Replaced by |
|------|-------|-------------|
| `shared/providers/pi/nativeAdapter.jsx` | 857 | useChat + PiAgentCoreTransport |
| `shared/providers/pi/backendAdapter.jsx` | 516 | useChat + DefaultChatTransport |
| `shared/components/chat/AiChat.jsx` | 299 | useChat + DefaultChatTransport |
| `shared/providers/pi/useChatTransport.js` | 73 | useAgentTransport |

**Verify all 4 URLs:**
- `?layout=chat&agent_mode=frontend`
- `?layout=chat&agent_mode=backend`
- `?layout=ide&agent_mode=frontend`
- `?layout=ide&agent_mode=backend`

---

## E2E Tests

16 Playwright tests across all 4 configs:

**UI smoke (12 tests):** NavRail, ChatStage, ChatComposer, dev banner, thinking toggle, model selector, session drawer, keyboard shortcuts

**Agent interaction (4 tests):** Create file → read back → open in editor → close/reopen Surface → list_tabs → cleanup

```bash
PW_CHAT_SMOKE_URL=http://host:port npx playwright test --config=playwright.smoke.config.js
```

---

## Open Items

| Item | Priority | Notes |
|------|----------|-------|
| `?chat=` param wiring | High | URL param parsed + shown in dev banner, but not yet wired to switch between pi-web and vercel-sdk chat interfaces |
| Session persistence (localStorage vs IndexedDB) | Medium | useSessionState uses localStorage, pi-web-ui uses IndexedDB. Migration path TBD. |
| XML tool normalization | Low | Edge case for LLMs that emit XML tool calls. `toolCallXmlTransform.js` exists but not wired into transport. |
| AgentPanel rewrite (Phase 3) | Blocked | Needs Phases 1-2 validated in production first. |
