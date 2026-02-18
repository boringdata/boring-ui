# Project Context

boring-ui is a composable, capability-gated web IDE framework. It provides a panel-based UI shell (React + DockView) backed by a modular FastAPI backend. Panels declare their backend requirements and the system automatically degrades gracefully when features are unavailable.

## What It Does

boring-ui gives you a browser-based IDE experience with:
- A file tree with git status integration
- A TipTap-based markdown/code editor
- Claude AI chat sessions via WebSocket streaming
- Shell terminals via PTY WebSocket
- A tool approval workflow for AI agent actions
- Companion and PI agent integrations (pluggable chat providers)
- Layout persistence with versioned migration and recovery

The key design property: you compose the backend from independent routers and the frontend adjusts automatically via capability gating.

## Stack

- **Frontend**: React 18, Vite 5, TailwindCSS 4, DockView (panel layout), Zustand (state), xterm.js (terminal), TipTap (editor)
- **Backend**: Python 3, FastAPI, uvicorn, ptyprocess (PTY), websockets
- **Tests**: Vitest (unit), Playwright (e2e), pytest (backend)
- **Build**: Vite for frontend (dev + lib modes), pip/pyproject.toml for backend
- **Deploy**: Local dev server or hosted mode with boring-sandbox control plane

## Two Operating Modes

- **LOCAL mode**: Backend runs in-process alongside the frontend dev server. File/git/PTY operations go directly to the local filesystem. No auth required.
- **HOSTED mode**: Backend runs behind a control plane (boring-sandbox). Auth via OIDC, workspace-scoped routing, capability tokens for privileged operations. Frontend rewrites API paths from `/api/*` to `/api/v1/*`.

## Repo Layout

```
boring-ui/
src/front/          React frontend (App.jsx, components, panels, hooks, layout, registry)
src/back/boring_ui/ Python backend (FastAPI app factory, config, modules)
docs/               Architecture, design docs, execution plans, runbooks
tests/              Backend pytest tests
scripts/            Gates, E2E runner, utilities
app.config.js       Frontend configuration overrides
vite.config.ts      Vite build configuration
pyproject.toml      Python packaging
```

## Key Abstractions

| Abstraction | Location | Purpose |
|---|---|---|
| PaneRegistry | `src/front/registry/panes.js` | Maps pane IDs to components + capability requirements |
| CapabilityGate | `src/front/components/CapabilityGate.jsx` | Wraps panes; shows error state when backend lacks required features |
| LayoutManager | `src/front/layout/LayoutManager.js` | Persists/restores/migrates DockView layout state |
| RouterRegistry | `src/back/boring_ui/api/capabilities.py` | Registers backend routers; powers `/api/capabilities` |
| APIConfig | `src/back/boring_ui/api/config.py` | Central config dataclass injected into all router factories |
| create_app() | `src/back/boring_ui/api/app.py` | Application factory wiring routers, middleware, and capabilities |

## Active Work

The current branch (`control-plan-decoupling`) is focused on service split and control-plane decoupling: separating boring-ui into distinct service boundaries (workspace-core, pty-service, agent-normal, agent-companion, agent-pi) and ensuring frontend networking goes through shared transport helpers rather than hardcoding gateway patterns. See `docs/SERVICE_SPLIT_AND_LEGACY_CLEANUP_PLAN.md` for the full plan.

## Related Repositories

- **boring-sandbox**: Control plane, gateway, auth, workspace lifecycle, sprite sandboxes
- **boring-coding**: Shared workflow docs, agent conventions, tooling
