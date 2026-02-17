


<!-- br-agent-instructions-v1 -->

---

## Beads Workflow Integration

This project uses [beads_rust](https://github.com/Dicklesworthstone/beads_rust) (`br`/`bd`) for issue tracking. Issues are stored in `.beads/` and tracked in git.

### Worker Execution Loop

Repeat until no beads remain:

1. **Pick & claim**: `bv --robot-next` → `br show <id>` (verify acceptance criteria + deps exist, fix before coding) → `br update <id> --claim --actor <name>` + announce in Agent Mail.
2. **Implement**: only the scoped bead — no unrelated refactors, **no stubs** (`pass`, `TODO`, `NotImplementedError`). If a piece can't be completed, split into a new bead. Self-review changed code: "Read over all new code you just wrote and existing code you modified with fresh eyes, looking carefully for any obvious bugs, errors, problems, issues, or confusion. Fix anything you uncover. Use ultrathink." Run verification commands (tests/lints). If no tests exist, add at least one.
3. **Commit & review**: commit only this bead's files (message MUST include bead-id + acceptance criteria). Then request a review: `roborev review HEAD` and iterate — read the review with `roborev show HEAD`, fix findings, commit the fix, review again — until the review passes (max 10 iterations). Use a cross-model reviewer (CC workers → `--agent codex`, Codex workers → `--agent claude`).
4. **Prove**: build evidence with Showboat (see guidelines below). `showboat verify` before closing. Link to bead: `br comments add <id> --message "EVIDENCE: .evidence/<bead-id>.md; review=roborev-passed"`.
5. **Close & notify**: `br close <id> --reason "implemented + reviewed + verified" --actor <name>`. Send Agent Mail summary (what changed, commit hash). Loop back to step 1.

### Evidence & Proof (Showboat + Rodney)

Use [Showboat](https://simonwillison.net/2026/Feb/10/showboat-and-rodney/) to capture proof, [Rodney](https://github.com/simonw/rodney) for browser screenshots. Run `showboat --help` / `rodney --help` for full usage.

```bash
# Proof flow: init → exec/image → verify → commit
showboat init .evidence/<bead-id>.md "<bead-id>: <title>"
showboat exec .evidence/<bead-id>.md bash "pytest tests/ -v"   # captures real output
rodney start && rodney open <url> && rodney screenshot .evidence/shot.png && rodney stop  # UI proof
showboat verify .evidence/<bead-id>.md                         # re-runs all, confirms reproducible
```

- **Where**: `.evidence/<bead-id>.md` — one file per bead, committed to git.
- **Rule**: always `showboat verify` before closing. Don't hand-edit evidence files.

### References

- **Priority**: P0=critical, P1=high, P2=medium, P3=low, P4=backlog (numbers 0-4)
- **Session end**: always `br sync --flush-only && git push` before ending.
- **New beads**: must include acceptance criteria in description. Use `br --help` for full CLI reference.

### Supabase Credentials (How To Get)

Fetch credentials from the agent secret store using these paths:

- `Project URL`: `secret/agent/boring-ui-supabase-project-url`
- `Publishable key`: `secret/agent/boring-ui-supabase-publishable-key`
- `Service role key`: `secret/agent/boring-ui-supabase-service-role-key`
- `DB password`: `secret/agent/boring-ui-supabase`
- `DB connection URL`: `secret/agent/boring-ui-supabase-db-url`

Security notes:

- Never commit secret values to git, issue comments, logs, or screenshots.
- Keep values in environment variables or local untracked `.env` files only.
- Rotate and re-fetch secrets if exposure is suspected.

<!-- end-br-agent-instructions -->

---

## Project Context

**boring-ui** is an extensible, browser-based IDE framework for building AI-powered coding environments.

- **Role**: Full-stack IDE shell — file browsing, editing, terminal, Claude chat, git integration
- **Stack**: React + Vite + DockView + Zustand (frontend) / FastAPI + Uvicorn (backend)
- **Two modes**: LOCAL (in-process, single-user) and HOSTED (control+data plane separation via boring-sandbox)
- **Control plane**: boring-sandbox handles auth, provisioning, and stream proxying for hosted mode

### Architecture Overview

| Layer | Tech | Key Files |
|-------|------|-----------|
| Frontend | React 18, Vite 5, DockView, Zustand, TipTap, xterm.js | `src/front/App.jsx`, `src/front/components/` |
| Backend | FastAPI, ptyprocess, websockets, PyJWT | `src/back/boring_ui/api/app.py` |
| Panel system | DockView + PaneRegistry with capability gating | `src/front/registry/panes.js` |
| Chat | Claude streaming via @assistant-ui/react | `src/front/components/chat/` |
| Auth | OIDC (hosted) / none (local) | `src/back/boring_ui/api/auth_middleware.py` |
| Observability | structlog, prometheus-client | `src/back/boring_ui/api/observability/` |

### Environment Setup

```bash
# Backend
pip3 install -e . --break-system-packages
export ANTHROPIC_API_KEY=$(vault kv get -field=api_key secret/agent/anthropic)
python3 -c "from boring_ui.api.app import create_app; import uvicorn; app = create_app(include_sandbox=True, include_companion=True); uvicorn.run(app, host='0.0.0.0', port=8000)"

# Frontend
npm install
npx vite --host 0.0.0.0 --port 5173
```

### Running Tests

```bash
# Python unit tests
python3 -m pytest tests/unit/ -v

# Frontend tests
npx vitest run

# E2E tests (requires running backend + frontend)
npx playwright test
```

### Key Directories

```
src/front/                  # React frontend
  components/               # UI components (FileTree, Editor, Terminal, etc.)
  components/chat/          # Claude chat integration
  hooks/                    # React hooks (useApiMode, useServiceConnection, etc.)
  panels/                   # DockView panel wrappers
  registry/                 # PaneRegistry with capability gating
  utils/                    # modeAwareApi, wsAuth, etc.

src/back/boring_ui/         # Python backend
  api/                      # FastAPI routes and middleware
    app.py                  # App factory
    config.py               # RunMode, APIConfig
    capabilities.py         # Mode + features + tokens endpoint
    v1_router.py            # Canonical /api/v1 routes
    auth_middleware.py       # OIDC auth + AuthContext
    capability_tokens.py    # CapabilityTokenIssuer/Validator
  local_api/                # Local in-process API
  modules/                  # Pluggable modules (companion, files, git, pty, sandbox, stream)
  observability/            # Structured logging, metrics, audit

src/control_plane/          # Hosted control plane (boring-sandbox consumes this)

tests/                      # Python tests (unit, integration, contract, security)
scripts/                    # Build, validation, and scenario scripts
docs/                       # Architecture docs and plans
```

### Mode-Aware API

- `buildApiUrl()` — for non-privileged calls (`/api/config`, `/api/search`, `/api/sessions`)
- `buildUrl()` from `useApiMode()` — for privileged calls (`/api/file`, `/api/tree`, `/api/git/*`); rewrites to `/api/v1/*` in hosted mode
- WebSocket auth in hosted mode uses query-param token (browser WS API limitation)
- Parity mode: `LOCAL_PARITY_MODE=http` exercises hosted code path locally
