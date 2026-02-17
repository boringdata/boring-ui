# Plan: Companion Claude Integration

## Goal

Add the Companion app as a distinct DockView panel in boring-ui. Companion is an upstream project providing a complete Claude Code web UI. By adopting it we stop maintaining our own Claude CLI frontend and can pull upstream improvements fast.

## Architecture

- **Companion is its own DockView panel** — registered in PaneRegistry like `terminal`, `shell`, `filetree`
- **Capability-gated** — panel only appears when `companion` feature is enabled (`COMPANION_URL` is set)
- **Companion runs as a separate service** — not managed by boring-ui backend
- **No auth** — Companion runs locally, no JWT/tokens
- **Upstream app as-is** — CompanionPanel renders upstream React app directly
- **Zero changes to TerminalPanel** — existing ClaudeStreamChat is untouched
- **Both can coexist** — Claude and Companion panels can be open side by side
- **No adapter/fetch layer** — CompanionPanel reads URL from existing CapabilitiesContext, sets it on upstream config module, renders `<CompanionApp />`

---

## Phase 1: Backend — Companion config in capabilities

### 1.1 Add `companion_url` to APIConfig

**File:** `src/back/boring_ui/api/config.py`

Add one field to the `APIConfig` dataclass after `pty_providers` (line 40):

```python
companion_url: str | None = field(
    default_factory=lambda: os.environ.get('COMPANION_URL')
)
```

---

### 1.2 Update capabilities endpoint to include services

**File:** `src/back/boring_ui/api/capabilities.py`

**Change 1:** Update `create_capabilities_router` signature (line 151) to accept config:

```python
def create_capabilities_router(
    enabled_features: dict[str, bool],
    registry: RouterRegistry | None = None,
    config: "APIConfig | None" = None,
) -> APIRouter:
```

**Change 2:** Inside `get_capabilities()`, after the `routers` block (after line 190), add:

```python
        # Service connection info for direct-connect panels
        if config and config.companion_url:
            capabilities['services'] = {
                'companion': {
                    'url': config.companion_url,
                },
            }
```

---

### 1.3 Wire config through app factory

**File:** `src/back/boring_ui/api/app.py`

**Change 1:** Add `companion` to `enabled_features` map (after line 106):

```python
        'companion': bool(config.companion_url),
```

**Change 2:** Pass config to capabilities router (line 180):

```python
    app.include_router(
        create_capabilities_router(enabled_features, registry, config),
        prefix='/api',
    )
```

---

## Phase 2: Frontend — Companion upstream app + config

### 2.1 Port upstream Companion app (vendored, read-only)

**Source:** `poc/opencode-web-chat:src/front/providers/companion/upstream/`
**Destination:** `src/front/providers/companion/upstream/`

Copy entire directory as-is. Use `git show` to extract each file:

```bash
mkdir -p src/front/providers/companion/upstream/components
mkdir -p src/front/providers/companion/upstream/utils

# Root files
for f in App.tsx api.ts ws.ts store.ts types.ts index.css main.tsx; do
  git show poc/opencode-web-chat:src/front/providers/companion/upstream/$f > src/front/providers/companion/upstream/$f
done

# Utils
git show poc/opencode-web-chat:src/front/providers/companion/upstream/utils/names.ts > src/front/providers/companion/upstream/utils/names.ts

# Components
for f in ChatView.tsx Composer.tsx EnvManager.tsx HomePage.tsx MessageBubble.tsx MessageFeed.tsx PermissionBanner.tsx Playground.tsx Sidebar.tsx TaskPanel.tsx ToolBlock.tsx TopBar.tsx; do
  git show poc/opencode-web-chat:src/front/providers/companion/upstream/components/$f > src/front/providers/companion/upstream/components/$f
done
```

**Do NOT copy test files** (api.test.ts, store.test.ts, ws.test.ts, test-setup.ts).

**Vite compatibility:** Upstream `.tsx` files work natively with Vite + `@vitejs/plugin-react`. Tailwind classes are pre-compiled in `upstream.css`.

---

### 2.2 Port upstream.css (compiled Tailwind)

**Source:** `poc/opencode-web-chat:src/front/providers/companion/upstream.css`
**Destination:** `src/front/providers/companion/upstream.css`

```bash
git show poc/opencode-web-chat:src/front/providers/companion/upstream.css > src/front/providers/companion/upstream.css
```

Pre-compiled Tailwind (~37KB). Scoped via `.provider-companion` wrapper class.

---

### 2.3 Create config.js

**File:** `src/front/providers/companion/config.js`

This is the glue between boring-ui and the upstream app. Upstream `ws.ts` and `api.ts` import `getCompanionBaseUrl()` and `getCompanionAuthToken()` from this module. CompanionPanel sets the values before upstream App mounts.

```js
let _baseUrl = ''
let _authToken = ''

export function setCompanionConfig(baseUrl, authToken) {
  _baseUrl = baseUrl || ''
  _authToken = authToken || ''
}

export function getCompanionBaseUrl() {
  return _baseUrl
}

export function getCompanionAuthToken() {
  return _authToken
}

export function getAuthHeaders() {
  if (!_authToken) return {}
  return { Authorization: `Bearer ${_authToken}` }
}
```

---

### 2.4 Create theme-bridge.css

**File:** `src/front/providers/companion/theme-bridge.css`

```css
.provider-companion {
  --color-cc-bg: var(--color-bg-primary);
  --color-cc-fg: var(--color-text-primary);
  --color-cc-card: var(--color-bg-secondary);
  --color-cc-primary: var(--color-accent, #ae5630);
  --color-cc-primary-hover: var(--color-accent-hover, #c4643a);
  --color-cc-user-bubble: var(--color-bg-tertiary, #DDD9CE);
  --color-cc-border: var(--color-border);
  --color-cc-muted: var(--color-text-tertiary);
  --color-cc-sidebar: var(--color-bg-secondary);
  --color-cc-input-bg: var(--color-bg-secondary);
  --color-cc-code-bg: var(--color-code-bg, #1e1e1e);
  --color-cc-code-fg: var(--color-code-fg, #d4d4d4);
  --color-cc-hover: var(--color-hover, rgba(0,0,0,0.04));
  --color-cc-active: var(--color-active, rgba(0,0,0,0.07));
  --color-cc-success: var(--color-success, #2d7d46);
  --color-cc-error: var(--color-error, #c53030);
  --color-cc-warning: var(--color-warning, #b7791f);
}
```

---

## Phase 3: Frontend — CompanionPanel + pane registration

### 3.1 Create CompanionPanel.jsx

**File:** `src/front/panels/CompanionPanel.jsx`

Reads Companion URL from existing `CapabilitiesContext` (already fetched by App.jsx). Sets it on the config module. Renders upstream App.

```jsx
import { useMemo } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useCapabilitiesContext } from '../components/CapabilityGate'
import { setCompanionConfig } from '../providers/companion/config'
import CompanionApp from '../providers/companion/upstream/App'
import '../providers/companion/upstream.css'
import '../providers/companion/theme-bridge.css'

export default function CompanionPanel({ params }) {
  const { collapsed, onToggleCollapse } = params || {}
  const capabilities = useCapabilitiesContext()
  const companionUrl = capabilities?.services?.companion?.url

  // Set config synchronously before CompanionApp renders.
  // useMemo runs during render, before children mount.
  const ready = useMemo(() => {
    if (companionUrl) {
      setCompanionConfig(companionUrl, '')
      return true
    }
    return false
  }, [companionUrl])

  if (collapsed) {
    return (
      <div className="panel-content terminal-panel-content terminal-collapsed">
        <button
          type="button"
          className="sidebar-toggle-btn"
          onClick={onToggleCollapse}
          title="Expand companion panel"
          aria-label="Expand companion panel"
        >
          <ChevronLeft size={16} />
        </button>
        <div className="sidebar-collapsed-label">Companion</div>
      </div>
    )
  }

  return (
    <div className="panel-content terminal-panel-content">
      <div className="terminal-header">
        <button
          type="button"
          className="sidebar-toggle-btn"
          onClick={onToggleCollapse}
          title="Collapse companion panel"
          aria-label="Collapse companion panel"
        >
          <ChevronRight size={16} />
        </button>
        <span className="terminal-title-text">Companion</span>
        <div className="terminal-header-spacer" />
      </div>
      <div className="terminal-body">
        <div className="terminal-instance active">
          {ready ? (
            <div className="provider-companion">
              <CompanionApp />
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--color-text-tertiary)' }}>
              Connecting to Companion server...
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
```

**No adapter, no useServiceConnection, no fetch.** Panel reads directly from context that App.jsx already provides.

---

### 3.2 Register companion pane in PaneRegistry

**File:** `src/front/registry/panes.js`

**Change 1:** Add import (after line 54):

```js
import CompanionPanel from '../panels/CompanionPanel'
```

**Change 2:** Add registration inside `createDefaultRegistry()` (after line 351, before `return registry`):

```js
  // Companion - alternative Claude chat panel (Direct Connect)
  registry.register({
    id: 'companion',
    component: CompanionPanel,
    title: 'Companion',
    placement: 'right',
    essential: false,
    locked: false,
    hideHeader: true,
    constraints: {
      minWidth: 250,
    },
    requiresFeatures: ['companion'],
  })
```

**Change 3:** Update JSDoc table (around line 269) to add:

```
 * | companion | no        | right     | companion feature      |
```

---

## Phase 4: Verification

### 4.1 Test without Companion (regression)
```bash
# No COMPANION_URL set
python3 -c "from boring_ui.api.app import create_app; import uvicorn; app = create_app(); uvicorn.run(app, host='0.0.0.0', port=8000)"
npx vite --host 0.0.0.0 --port 5173
```
- `GET /api/capabilities` should NOT have `companion` in features or `services`
- Companion pane should NOT appear
- All existing panels work as before

### 4.2 Test with Companion
```bash
export COMPANION_URL=http://localhost:3456
python3 -c "from boring_ui.api.app import create_app; import uvicorn; app = create_app(); uvicorn.run(app, host='0.0.0.0', port=8000)"
npx vite --host 0.0.0.0 --port 5173
```
- `GET /api/capabilities` returns `features.companion: true` and `services.companion.url`
- Companion pane appears in DockView
- CompanionApp connects to Companion WebSocket
- End-to-end: send message, get Claude response

### 4.3 Test coexistence
- Both `terminal` (Claude) and `companion` panels open side by side
- Verify they work independently

### 4.4 Test graceful fallback
- `COMPANION_URL` set but Companion server not running
- Panel shows "Connecting to Companion server..." (not crash)

---

## File Inventory

### New files (create from scratch)
```
src/front/panels/CompanionPanel.jsx              # ~65 lines — panel reads context, renders upstream App
src/front/providers/companion/config.js          # ~20 lines — module-level URL store for upstream imports
src/front/providers/companion/theme-bridge.css   # ~20 lines — CSS variable bridge
```

### New files (copy from POC as-is)
```
src/front/providers/companion/upstream.css       # ~37KB — pre-compiled Tailwind
src/front/providers/companion/upstream/App.tsx
src/front/providers/companion/upstream/api.ts
src/front/providers/companion/upstream/ws.ts
src/front/providers/companion/upstream/store.ts
src/front/providers/companion/upstream/types.ts
src/front/providers/companion/upstream/index.css
src/front/providers/companion/upstream/main.tsx
src/front/providers/companion/upstream/utils/names.ts
src/front/providers/companion/upstream/components/ChatView.tsx
src/front/providers/companion/upstream/components/Composer.tsx
src/front/providers/companion/upstream/components/EnvManager.tsx
src/front/providers/companion/upstream/components/HomePage.tsx
src/front/providers/companion/upstream/components/MessageBubble.tsx
src/front/providers/companion/upstream/components/MessageFeed.tsx
src/front/providers/companion/upstream/components/PermissionBanner.tsx
src/front/providers/companion/upstream/components/Playground.tsx
src/front/providers/companion/upstream/components/Sidebar.tsx
src/front/providers/companion/upstream/components/TaskPanel.tsx
src/front/providers/companion/upstream/components/ToolBlock.tsx
src/front/providers/companion/upstream/components/TopBar.tsx
```

### Modified files
```
src/back/boring_ui/api/config.py         # +3 lines: companion_url field
src/back/boring_ui/api/capabilities.py   # +8 lines: config param + services block
src/back/boring_ui/api/app.py            # +2 lines: companion feature + pass config
src/front/registry/panes.js              # +14 lines: import + register companion pane
```

---

## Dependencies / Gotchas

| Issue | Resolution |
|-------|------------|
| Upstream `ws.ts`/`api.ts` import `../config.js` | `config.js` provides `getCompanionBaseUrl()` — set by CompanionPanel before App mounts via `useMemo` |
| Upstream `api.ts` sends auth headers | `getAuthHeaders()` returns `{}` when token empty — no-op |
| Upstream uses Tailwind classes | Pre-compiled into `upstream.css`, scoped to `.provider-companion` |
| Upstream `.tsx` files | Vite handles natively — verify `@vitejs/plugin-react` in vite.config |
| `upstream.css` is ~37KB | One-time load, scoped. Acceptable. |
| No `apiFetch` on this branch | Not needed — CompanionPanel reads from CapabilitiesContext (already fetched) |
| No `shared/renderers` on this branch | Not needed — upstream has its own renderers (ToolBlock.tsx, MessageBubble.tsx) |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COMPANION_URL` | (none) | Companion server URL. When set, enables the Companion panel. |

---

## Out of Scope

- Any changes to TerminalPanel or ClaudeStreamChat
- Adapter / useServiceConnection / fetch layers
- ChatProviderRegistry abstractions
- Companion lifecycle management (start/stop)
- Auth/JWT tokens
- Backend companion router endpoints
- Upstream customization beyond CSS theming
