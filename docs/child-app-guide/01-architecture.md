# 1. Architecture Overview

[< Back to Index](README.md) | [Next: Scaffolding >](02-scaffolding.md)

---

A boring-ui child app extends boring-ui at three layers:

```
┌──────────────────────────────────────┐
│          Your Child App              │
│  ┌────────────┐  ┌────────────────┐  │
│  │  Backend    │  │   Frontend     │  │
│  │  (FastAPI)  │  │   (React)      │  │
│  │  - config   │  │  - panels      │  │
│  │  - routers  │  │  - app.config  │  │
│  │  - runtime  │  │  - registry    │  │
│  └──────┬─────┘  └───────┬────────┘  │
│         │                │           │
│  ┌──────┴────────────────┴────────┐  │
│  │        boring-ui (submodule)   │  │
│  │  - create_app() factory        │  │
│  │  - core modules (files, git,   │  │
│  │    pty, auth, control plane)   │  │
│  │  - React framework (DockView,  │  │
│  │    ConfigProvider, pane reg.)  │  │
│  │  - deploy tooling              │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
```

## Key Principles

- **boring-ui provides workspace infrastructure** — files, git, terminals, auth, layout, DockView panels
- **Your app adds domain-specific logic** — backend routers under `/api/v1/your-domain/*` and frontend panels registered via `registerPane()`
- **Configuration flows through env vars** — boring-ui reads `APIConfig`, your app reads its own config dataclass, both resolved from environment
- **Capabilities drive the UI** — `/api/capabilities` is the single source of truth; frontend panels declare requirements and auto-degrade if unmet
- **Two deploy modes:**
  - **Core** — direct ASGI on Modal (simplest: your FastAPI serves API + static frontend)
  - **Edge** — through boring-sandbox gateway (isolated workspaces per user, full sandboxing)

## Integration Points

| Layer | boring-ui provides | Your app adds |
|-------|-------------------|---------------|
| **Backend** | `create_app()` factory, file/git/pty/auth routers, control plane | Domain routers, config, capabilities patches, companion proxy |
| **Frontend** | `App` shell, `ConfigProvider`, `registerPane()`, DockView layout, built-in panels | Custom panels, `app.config.js` overrides, pane registry overrides |
| **Deploy** | `mount_static()`, `package_app_assets.py`, edge bundle scripts | `modal_app.py`, `deploy.sh`, `deploy.env`, `app.toml` |

## Submodule Hierarchy

```
your-app/
└── interface/boring-ui/              # Git submodule
    └── vendor/boring-sandbox/        # Nested submodule (edge mode only)
```

- boring-ui is always required
- boring-sandbox is only needed for edge deploy (auto-initialized by `deploy/edge/deploy.sh`)
