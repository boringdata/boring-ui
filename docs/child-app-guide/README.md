# Building a boring-ui Child App

Complete guide to creating a new application on top of boring-ui. Covers project setup, backend integration, frontend customization, deployment, and infrastructure. Written so an agent (or human) can bootstrap a new app from scratch.

**Reference implementation:** [boring-macro](https://github.com/boringdata/boring-macro) — a macro research workbench built on boring-ui.

---

## Guide Index

| # | Section | What it covers |
|---|---------|----------------|
| [01](01-architecture.md) | **Architecture** | Three-layer model, key principles, how child apps extend boring-ui |
| [02](02-scaffolding.md) | **Project Scaffolding** | Directory structure, git init, submodule setup, index.html, package.json |
| [03](03-backend.md) | **Backend Integration** | App factory, config resolution, runtime.py, domain routers, companion agent, `create_app()` reference |
| [04](04-frontend.md) | **Frontend Integration** | main.jsx bootstrap, app.config.js, pane registry, custom panels, Vite config, available imports |
| [05](05-configuration.md) | **Configuration System** | Env var flow, capabilities-driven UI, key env vars reference |
| [06](06-deployment.md) | **Deployment** | Core mode (direct Modal ASGI), edge mode (boring-sandbox gateway), shared helpers |
| [07](07-infrastructure.md) | **Infrastructure & Secrets** | Neon (recommended), Supabase (legacy), Modal secrets, Vault, Resend email |
| [08](08-database.md) | **Database & Migrations** | Control plane schema, domain DB options (Neon, Supabase, ClickHouse, DuckDB) |
| [09](09-build-packaging.md) | **Build & Packaging** | Frontend build, wheel build, smoke tests |
| [10](10-testing.md) | **Testing** | Backend tests, frontend tests |
| [11](11-checklist.md) | **Checklist** | 25-item step-by-step checklist to create a new app from zero |
| [12](12-patterns.md) | **Common Patterns** | Capabilities patching, multi-mode frontend, auth redirect, dev session, WebSocket, ownership rules |

---

## Quick Start

If you just want to get going fast, follow the [Checklist](11-checklist.md) — it references the other sections for details.

## Architecture at a Glance

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

## See Also

- [EXTENSION_GUIDE.md](../references/EXTENSION_GUIDE.md) — Pane registry, layout, and config reference
- [ARCHITECTURE.md](../ARCHITECTURE.md) — boring-ui architecture overview
- [PROJECT_CONTEXT.md](../PROJECT_CONTEXT.md) — boring-ui project goals
- [runbooks/MODES_AND_PROFILES.md](../runbooks/MODES_AND_PROFILES.md) — Deploy modes explained
