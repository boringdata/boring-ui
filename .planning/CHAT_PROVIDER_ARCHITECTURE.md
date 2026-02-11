# Plan: Extensible Chat Provider Architecture + Inspector Port

## Context

boring-ui needs to host multiple chat UIs (ClaudeStreamChat, sandbox-agent inspector, Companion) that all evolve independently upstream. The current approach hardcodes two providers with `if/else` in TerminalPanel. We need:

1. **Easy upstream sync** — provider code stays close to original, `cp -r` to update
2. **Good integration** — proper theming, not iframes
3. **Extensible** — adding a new provider = register it, done

## Alternatives Studied

### sandbox-agent Inspector
- [github.com/rivet-dev/sandbox-agent](https://github.com/rivet-dev/sandbox-agent) — multi-agent chat UI
- Stack: React + TypeScript + plain CSS
- Protocol: REST + SSE via `sandbox-agent` SDK (universal schema)
- Agents: Claude Code, Codex, OpenCode, Amp, Mock
- 25 source files, full protocol: streaming modes (poll/SSE/turn), permissions, questions, content parts, debug panel
- Already integrated in boring-ui backend via `/api/sandbox/*` proxy

### The Vibe Companion
- [github.com/The-Vibe-Company/companion](https://github.com/The-Vibe-Company/companion) — Claude Code web interface
- Stack: Bun + Hono + React 19 + Zustand + Tailwind v4
- Protocol: WebSocket NDJSON (reverse-engineered `--sdk-url` flag — same protocol as boring-ui's ClaudeStreamChat)
- Claude Code only (single agent)
- Richer rendering: tool grouping, thinking blocks, markdown, cost stats, slash commands
- Very similar to existing ClaudeStreamChat — same underlying approach

### Verdict
Inspector = multi-agent via official SDK (different from what we have). Companion = same approach as ClaudeStreamChat (better polish). Both worth integrating. Architecture must support both.

## Architecture: ChatProviderRegistry

Mirror the existing `PaneRegistry` pattern (`src/front/registry/panes.js`). Each chat provider is a self-contained module that registers itself.

### Provider Contract

```js
{
  id: 'inspector',              // unique key
  label: 'Inspector',           // display name
  component: InspectorAdapter,  // React component
  requiresCapabilities: [],     // capability gating (like PaneRegistry)
}
```

### File Structure

```
src/front/
  providers/
    registry.js                    # ChatProviderRegistry (follows PaneRegistry pattern)

    claude/
      index.js                     # register({ id: 'claude', component: ClaudeAdapter })
      adapter.jsx                  # thin wrapper → existing ClaudeStreamChat

    inspector/
      index.js                     # register({ id: 'inspector', component: InspectorAdapter })
      adapter.jsx                  # wraps upstream App in .provider-inspector div
      theme-bridge.css             # maps boring-ui CSS vars → inspector CSS vars
      upstream/                    # VERBATIM copy of inspector/src/ (TSX stays TSX)
        App.tsx
        components/chat/*.tsx
        components/debug/*.tsx
        components/ConnectScreen.tsx
        components/SessionSidebar.tsx
        components/agents/*.tsx
        lib/permissions.ts
        types/*.ts
        utils/*.ts
      upstream.css                 # extracted from inspector index.html <style>

    companion/                     # (future — Phase 3)
      index.js
      adapter.jsx
      theme-bridge.css
      upstream/                    # VERBATIM copy of companion/web/src/
```

### How Upstream Sync Works

Each `upstream/` directory is a verbatim copy. To update:
```bash
# Inspector
cp -r poc/sandbox-agent/frontend/packages/inspector/src/* \
      src/front/providers/inspector/upstream/

# Companion (future)
cp -r vendor/companion/web/src/* \
      src/front/providers/companion/upstream/
```

Only 3 files per provider are boring-ui-specific: `index.js`, `adapter.jsx`, `theme-bridge.css`. The upstream code is untouched.

### CSS Isolation via Theme Bridge

Each provider gets a scoping class + CSS variable mapping:

```css
/* providers/inspector/theme-bridge.css */
.provider-inspector {
  --bg: var(--color-bg-primary);
  --surface: var(--color-bg-secondary);
  --border: var(--color-border);
  --text: var(--color-text-primary);
  --muted: var(--color-text-tertiary);
  --accent: var(--color-accent);
  /* ... etc */
}
```

Adapter wraps upstream component: `<div className="provider-inspector"><InspectorApp /></div>`

### TerminalPanel Refactoring

Replace hardcoded `if (chatProvider === 'sandbox')` with registry lookup:

```jsx
import chatProviders from '../providers/registry'

const provider = chatProviders.get(chatProvider)
const ChatComponent = provider?.component
// render <ChatComponent /> with standard props
```

## Backend Integration

Each provider's backend stays independent (no shared abstraction):

| Provider | Backend Module | Routes | Capability Flag |
|---|---|---|---|
| Claude | `modules/chat_claude_code/` (exists) | `/api/ws/claude/{session}` | `chat_claude_code` |
| Inspector | `modules/sandbox/` (exists) | `/api/sandbox/*` proxy | `sandbox` |
| Companion | `modules/companion/` (future) | `/api/companion/*` | `companion` |

**Remote sandbox security**: Backend proxy is the security boundary. Sandbox tokens stored server-side, injected by proxy. Frontend talks only to `/api/{provider}/*`, never directly to sandbox. The existing `SandboxProvider` abstraction (`LocalProvider`, `ModalProvider`) already handles local vs remote.

## Implementation Phases

### Phase 1: Foundation (no behavior change)

**Create registry + adapters for existing providers:**
1. Create `src/front/providers/registry.js` — ChatProviderRegistry class
2. Create `src/front/providers/claude/index.js` + `adapter.jsx` — wraps existing ClaudeStreamChat
3. Create `src/front/providers/sandbox/index.js` + `adapter.jsx` — wraps existing SandboxChat (temporary)
4. Refactor `src/front/panels/TerminalPanel.jsx` — use registry lookup instead of if/else
5. Verify: `npx vite build` passes, behavior identical

### Phase 2: Inspector port

**Port full inspector UI as upstream/ verbatim copy:**
1. `npm install sandbox-agent` — add SDK
2. Copy all 25 inspector source files to `providers/inspector/upstream/` (keep TSX)
3. Extract CSS from `poc/sandbox-agent/frontend/packages/inspector/index.html` → `upstream.css`
4. Create `theme-bridge.css` — map boring-ui vars to inspector vars
5. Create `adapter.jsx` — wrap Inspector App with theme bridge
6. Create `index.js` — register provider
7. Update `appConfig.js` — add `'inspector'` as provider option
8. Verify: `npx vite build`, browser test with `config.chat.provider = 'inspector'`

### Phase 3: Companion (future)
### Phase 4: Shared tool renderer bridges (future)

## Files Modified

- `src/front/panels/TerminalPanel.jsx` — replace if/else with registry lookup
- `src/front/config/appConfig.js` — extend provider options
- `package.json` — add `sandbox-agent` dependency

## Files Created

**Registry (1 file):**
- `src/front/providers/registry.js`

**Claude provider (2 files):**
- `src/front/providers/claude/index.js`
- `src/front/providers/claude/adapter.jsx`

**Sandbox temp provider (2 files):**
- `src/front/providers/sandbox/index.js`
- `src/front/providers/sandbox/adapter.jsx`

**Inspector provider (3 + 25 upstream files):**
- `src/front/providers/inspector/index.js`
- `src/front/providers/inspector/adapter.jsx`
- `src/front/providers/inspector/theme-bridge.css`
- `src/front/providers/inspector/upstream.css`
- `src/front/providers/inspector/upstream/` — 25 files verbatim from inspector

## Verification

1. `npx vite build` — zero errors
2. `config.chat.provider = 'claude'` — ClaudeStreamChat works as before
3. `config.chat.provider = 'sandbox'` — existing SandboxChat works as before
4. `config.chat.provider = 'inspector'` — full inspector UI renders in terminal panel
