# 11. Checklist: New App from Scratch

[< Back to Index](README.md) | [Prev: Testing](10-testing.md) | [Next: Patterns >](12-patterns.md)

---

Use this checklist when creating a new boring-ui child app. Each item links to the relevant guide section for details.

## Project Setup

- [ ] `git init` + add boring-ui submodule (`interface/boring-ui/`) — [Scaffolding](02-scaffolding.md#step-1-initialize-the-repository)
- [ ] Create `.gitignore` (node_modules, dist, .env, .venv, __pycache__) — [Scaffolding](02-scaffolding.md#step-1-initialize-the-repository)
- [ ] Create `src/web/index.html` — [Scaffolding](02-scaffolding.md#step-2-create-srcwebindexhtml)
- [ ] Create `src/web/package.json` with `boring-ui: file:../../interface/boring-ui` — [Scaffolding](02-scaffolding.md#step-3-create-srcwebpackagejson)
- [ ] Create `src/web/vite.config.js` with `@boring-ui` alias + `dedupe` + workspace proxy rules — [Frontend](04-frontend.md#45-vite-config-srcwebviteconfigjs)
- [ ] Create `src/web/.env.example` — [Scaffolding](02-scaffolding.md#step-4-create-srcwebenvexample)
- [ ] Create Python venv + install backend deps (`fastapi`, `uvicorn`, `python-dotenv`, etc.) — [Scaffolding](02-scaffolding.md#step-5-install-dependencies)
- [ ] `cd src/web && npm install` — [Scaffolding](02-scaffolding.md#step-5-install-dependencies)

## Backend

- [ ] Create `src/web/backend/__init__.py` — [Scaffolding](02-scaffolding.md#step-6-create-backend-skeleton)
- [ ] Create `src/web/backend/config.py` with `get_config()` and `normalize_deploy_env()` — [Backend](03-backend.md#32-configuration-backendconfigpy)
- [ ] Create `src/web/backend/app.py` with `create_app()` wrapping boring-ui — [Backend](03-backend.md#31-the-app-factory-backendapppy)
- [ ] Create `src/web/backend/runtime.py` with static mount — [Backend](03-backend.md#33-production-runtime-backendruntimepy)
- [ ] Create domain router(s) under `src/web/backend/modules/` — [Backend](03-backend.md#34-domain-router-backendmodulesmy_domainrouterpy)
- [ ] Patch `/api/capabilities` to advertise domain features — [Patterns](12-patterns.md#121-patching-apicapabilities)

## Frontend

- [ ] Create `src/web/frontend/main.jsx` — imports ConfigProvider + App — [Frontend](04-frontend.md#41-main-entry-frontendmainjsx)
- [ ] Create `src/web/frontend/app.config.js` — branding, panels, features — [Frontend](04-frontend.md#42-app-config-frontendappconfigjs)
- [ ] Create `src/web/frontend/registry.js` — register custom panes — [Frontend](04-frontend.md#43-pane-registry-frontendregistryjs)
- [ ] Create panel components in `src/web/frontend/panels/` — [Frontend](04-frontend.md#44-custom-panel-component)
- [ ] (Optional) Override `empty` pane with app-specific welcome screen — [Frontend](04-frontend.md#43-pane-registry-frontendregistryjs)

## Deploy

- [ ] Create `deploy/shared/_deploy_common.sh` — [Deployment](06-deployment.md#63-shared-deploy-helpers-deployshared_deploy_commonsh)
- [ ] Create `deploy/core/deploy.sh` + `deploy.env` + `modal_app.py` — [Deployment](06-deployment.md#61-core-mode-direct-asgi)
- [ ] (Optional) Create `deploy/edge/` for sandbox mode — [Deployment](06-deployment.md#62-edge-mode-sandbox-gateway)
- [ ] Create Modal secrets (`my-app-secrets`) — [Infrastructure](07-infrastructure.md#73-modal-secrets)

## Infrastructure

- [ ] (If auth needed) Create Neon project + enable Neon Auth — [Infrastructure](07-infrastructure.md#71-neon-auth--database--recommended)
- [ ] (If auth needed) Run control plane migrations against your database — [Database](08-database.md#81-control-plane-neon-or-supabase)
- [ ] (If auth needed) Set `BORING_UI_SESSION_SECRET` to a stable value (not random) — [Configuration](05-configuration.md#55-auth-session-details)
- [ ] (If email needed) Configure Resend or email provider — [Infrastructure](07-infrastructure.md#74-email-resend)
- [ ] Store all secrets in Vault / Modal secrets — [Infrastructure](07-infrastructure.md)

## Testing

- [ ] Create smoke test script — [Build & Packaging](09-build-packaging.md#93-smoke-tests)
- [ ] Create backend unit tests — [Testing](10-testing.md#101-backend-tests)
- [ ] Verify `npm run dev:full` works locally

## Documentation

- [ ] Create `CLAUDE.md` with project-specific instructions
- [ ] Create `AGENTS.md` with safety rules and index
- [ ] Create `src/web/.env.example` documenting all env vars
