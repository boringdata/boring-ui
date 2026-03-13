# BUI Framework Plan

**Goal**: Make boring-ui a consumable framework with a Go CLI (`bui`), so child apps like boring-macro extend it via a single `boring.app.toml` config file. No submodules, no package registries.

**Key insight**: boring-ui is already modular (RouterRegistry, PaneRegistry, capabilities, pluggable auth/data). The work is config contract + CLI.

---

## Architecture

```
boring-ui (framework repo)
├── boring.app.toml              # Self-describing config (boring-ui runs off its own)
├── bui/                         # Go CLI source
├── src/back/boring_ui/          # Python backend (pip-installable)
├── src/front/                   # React frontend
└── pyproject.toml + package.json

boring-macro (child app repo)
├── boring.app.toml              # Declares framework ref, routers, panels, CLI commands, deploy
├── boring_macro/routers/        # Custom FastAPI routers
├── panels/                      # Custom React panels
├── pyproject.toml               # Child app's own deps (NOT boring-ui — bui handles that)
├── package.json                 # Child app's own deps (NOT boring-ui — bui handles that)
└── src/main.rs                  # Optional app-specific CLI (Rust, Go, whatever)
```

## How `bui` resolves boring-ui

boring-ui is NOT a dependency in pyproject.toml or package.json. `bui` manages it:

```
bui dev
│
├─ Read boring.app.toml → [framework].repo + [framework].commit
├─ Look for local checkout:
│   1. ../boring-ui exists?          → use it (auto-detect, best for dev)
│   2. BUI_FRAMEWORK_PATH env set?   → use that path
│   3. Neither?                      → clone/fetch to ~/.bui/cache/<commit>
├─ Create/activate .venv if not active (per-project isolation)
├─ pip install -e <resolved-path>    (editable, backend available instantly)
├─ Symlink <resolved-path> into node_modules/boring-ui (vite resolves imports)
└─ Continue with dev
```

**Auto-detect rule**: If `../boring-ui/` exists and has a `boring.app.toml`, use it. No config needed. Just have both repos side by side.

---

## Dev Workflow

```bash
# Setup: just clone repos side by side
~/projects/
├── boring-ui/         # framework
└── boring-macro/      # child app

# Dev (fast iteration)
cd boring-macro
bui dev
# → auto-detects ../boring-ui
# → creates .venv, pip install -e ../boring-ui
# → symlinks node_modules/boring-ui → ../boring-ui
# → starts uvicorn --reload (port 8000)
# → starts vite dev (port 5173, proxies /api→8000)
# → edit boring-ui OR boring-macro → instant hot-reload

# Local secrets via .env (no Vault needed in dev)
cat .env
ANTHROPIC_API_KEY=sk-...
BORING_SESSION_SECRET=dev-secret

# Debug (nothing special — standard tools)
bui dev --backend-only           # just uvicorn, attach debugger
bui dev --frontend-only          # just vite, use browser DevTools
# Or skip bui entirely:
uvicorn boring_macro.app:app --reload --port 8000
npx vite --port 5173

# Agent usage
bui info                         # parsed config: name, routers, panels, commands
bui run sql "SELECT ..."         # executes [cli.commands].sql
bui status                       # backend up? frontend up? neon connected?
```

## Deploy Workflow

**Dev = auto-detect local ../boring-ui. Deploy = always pinned [framework].commit.**

```bash
# 1. Push boring-ui changes
cd ../boring-ui && git push

# 2. Update pin (or let bui do it)
bui upgrade          # pulls latest boring-ui main, updates [framework].commit

# 3. Deploy (builds inside image — hermetic)
bui deploy           # resolves secrets, builds + deploys in one step
```

### What `bui deploy` does internally

```
bui deploy
│
├─ Read boring.app.toml
│   └─ [framework].commit = "8425471"  (ALWAYS uses pin, never ../boring-ui)
│
├─ Safety check: if ../boring-ui exists AND HEAD != pinned commit
│   └─ WARN: "Local boring-ui is at abc1234 but deploy pins 8425471. Run bui upgrade?"
│
├─ Resolve [deploy.secrets] from Vault
│   └─ ANTHROPIC_API_KEY, BORING_SESSION_SECRET, GITHUB_TOKEN (for private repo clone)
│
├─ Generate Modal image definition (hermetic — builds inside image):
│     FROM python:3.11-slim
│     ARG GITHUB_TOKEN
│     RUN pip install "boring-ui @ git+https://${GITHUB_TOKEN}@github.com/boringdata/boring-ui.git@8425471"
│     COPY . /app
│     RUN pip install /app
│     RUN cd /app && npm ci && npx vite build --outDir /app/static
│     ENV BORING_SESSION_SECRET=<from vault>
│     ENV ANTHROPIC_API_KEY=<from vault>
│     CMD ["python", "-c", "from boring_ui.app_config_loader import create_app_from_toml; ..."]
│
├─ modal deploy (or docker build+push)
│
└─ Health check → print URL
```

Build happens inside the image — hermetic, reproducible. No local `dist/` needed.
GITHUB_TOKEN injected as build arg for private repo access.

---

## Phase 1: Config Contract (`boring.app.toml`)

**What**: The single file a child app provides. `bui` reads it and wires everything.

- [ ] Finalize TOML schema (see spec below)
- [ ] Python `load_app_config("boring.app.toml")` → returns `APIConfig` + imports routers
- [ ] Frontend config: `bui dev` serves as JSON at `/__bui/config`; build injects as `window.__BUI_CONFIG__` in index.html
- [ ] Panel registration: `[frontend.panels]` → generates `_bui_panels.js` (one-time import)
- [ ] Self-hosting test: boring-ui boots from its own `boring.app.toml`

### Config spec

```toml
[app]
name = "boring-macro"
logo = "M"
id   = "boring-macro"

[framework]
repo   = "github.com/boringdata/boring-ui"
commit = "8425471"                          # pinned for deploy; ignored when ../boring-ui exists

[backend]
port    = 8000
routers = [                                 # Python dotted paths
    "boring_macro.routers.macro:router",
    "boring_macro.routers.transform:router",
]

[frontend]
port = 5173

[frontend.branding]
name = "boring-macro"

[frontend.features]
agentRailMode = "companion"

[frontend.data]
backend = "http"

[frontend.panels]
data-catalog = { component = "./panels/DataCatalog.jsx", title = "Data Catalog", placement = "left" }
chart-canvas = { component = "./panels/ChartCanvas.jsx", title = "Charts", placement = "center" }
deck         = { component = "./panels/Deck.jsx", title = "Deck", placement = "center" }

[cli.commands]
ingest  = { run = "bm ingest",  description = "Ingest FRED series into DuckDB" }
sql     = { run = "bm sql",     description = "Run SQL query against macro data" }
train   = { run = "bm train",   description = "Train forecast model" }
refresh = { run = "bm refresh", description = "Refresh all data sources" }

[auth]
provider       = "neon"                     # "neon" | "local" | "none"
session_cookie = "boring_session"
session_ttl    = 86400

[deploy]
platform = "modal"

[deploy.secrets]
ANTHROPIC_API_KEY     = { vault = "secret/agent/anthropic", field = "api_key" }
BORING_SESSION_SECRET = { vault = "secret/shared/session", field = "secret" }
GITHUB_TOKEN          = { vault = "secret/agent/boringdata-agent", field = "token" }

[deploy.neon]
project  = "boring-macro-prod"
database = "boring_macro"
# auth_url, database_url, jwks_url populated by `bui neon setup`

[deploy.modal]
app_name       = "boring-macro"
min_containers = 1
```

**Files**:
- `boring.app.toml` (root)
- `src/back/boring_ui/app_config_loader.py` (new: TOML → APIConfig + router imports)

---

## Phase 2: `bui` CLI (Go)

**What**: Single binary that reads `boring.app.toml` and orchestrates everything.

### 2a: Core (build first)
- [ ] `bui dev` — auto-detects ../boring-ui, creates .venv, installs editable, symlinks node_modules, spawns uvicorn + vite
- [ ] `bui dev` — reads `.env` for local secrets (no Vault needed in dev)
- [ ] `bui dev --backend-only` / `--frontend-only` — for debugging
- [ ] `bui info` — prints parsed config (name, routers, panels, commands) — agent reads this
- [ ] `bui run <cmd>` — executes `[cli.commands]` entry — agent uses this
- [ ] `bui status` — is backend up? frontend up? neon connected?
- [ ] `bui upgrade` — pulls latest boring-ui, updates [framework].commit
- [ ] `bui doctor` — checks everything is wired correctly:
  - Python found? Version ok?
  - Node found? Version ok?
  - ../boring-ui exists? HEAD vs pinned commit?
  - .venv exists? boring-ui installed?
  - node_modules/boring-ui symlink valid?
  - .env exists? Required secrets present?
  - boring.app.toml valid? Routers importable? Panels exist?
  - Ports 8000/5173 available?

### 2b: Deploy
- [ ] `bui deploy` — resolves secrets, builds inside image (hermetic), deploys
  - Warns if local ../boring-ui HEAD != pinned commit
  - Injects GITHUB_TOKEN as build arg for private repo access
- [ ] `bui neon setup` — provisions Neon project + DB + auth, prints TOML block
- [ ] `bui neon status` — checks Neon connection health

### 2c: Scaffold
- [ ] `bui init <name>` — generates child app skeleton

**Install**: `cd bui && go build -o bui . && cp bui /usr/local/bin/`

**Files**: `bui/` (already scaffolded: main.go, cmd/, config/, vault/, process/)

### Framework resolution logic (in Go)

```go
func resolveFramework(config AppConfig, mode string) string {
    if mode == "deploy" {
        // Deploy ALWAYS uses pinned commit
        return fetchToCache(config.Framework.Repo, config.Framework.Commit)
    }

    // Dev mode: auto-detect local checkout
    // 1. Sibling directory
    if exists("../boring-ui/boring.app.toml") {
        localHead := gitHead("../boring-ui")
        if localHead != config.Framework.Commit {
            warn("../boring-ui is at %s, config pins %s", localHead, config.Framework.Commit)
        }
        return "../boring-ui"
    }
    // 2. Explicit override
    if env("BUI_FRAMEWORK_PATH") != "" {
        return env("BUI_FRAMEWORK_PATH")
    }
    // 3. Fetch from git to cache
    return fetchToCache(config.Framework.Repo, config.Framework.Commit)
}
```

### Frontend symlink strategy

```go
func linkFrontend(frameworkPath string, childAppPath string) {
    // Create symlink so vite/IDE/TypeScript resolves boring-ui imports
    // node_modules/boring-ui → <frameworkPath>
    target := filepath.Join(childAppPath, "node_modules", "boring-ui")
    os.Remove(target)
    os.Symlink(frameworkPath, target)
    // Now: import { App } from 'boring-ui' → resolves to ../boring-ui/src/front/index.js
    // IDEs, TypeScript, ESLint all work
}
```

### Venv isolation

```go
func ensureVenv(childAppPath string) string {
    venvPath := filepath.Join(childAppPath, ".venv")
    if !exists(venvPath) {
        exec("python3 -m venv " + venvPath)
    }
    return filepath.Join(venvPath, "bin", "python")
    // All pip install commands use this python
    // No global site-packages pollution
    // Two child apps can run simultaneously without conflict
}
```

---

## Phase 3: Migrate boring-macro

**What**: Prove it works end-to-end.

- [ ] Remove `interface/boring-ui/` git submodule from boring-macro
- [ ] Remove boring-ui from pyproject.toml + package.json deps (bui handles it)
- [ ] Create `boring.app.toml` in boring-macro root
- [ ] Create `.env` with dev secrets
- [ ] Verify: `bui dev` starts boring-macro (auto-detects ../boring-ui)
- [ ] Verify: `bui deploy` builds inside image and deploys to Modal
- [ ] Verify: agent can `bui run sql "SELECT ..."` and `bui info`

---

## Priority Order

1. **Phase 1** (config contract) — foundation
2. **Phase 2a** (bui dev/info/run) — immediate dev experience
3. **Phase 3** (migrate boring-macro) — proves it works
4. **Phase 2b** (deploy) — can be manual initially
5. **Phase 2c** (scaffold) — nice-to-have

---

## Decisions Made

| Decision | Rationale |
|---|---|
| Go for CLI | Single binary, easy local install, fast startup, no runtime deps |
| No package registry | Private repos — git refs are sufficient |
| No versioning | Git commit/tag = version. Auto-detect local for dev, pin commit for deploy |
| `bui` manages boring-ui | Not in pyproject.toml/package.json. `bui` resolves, installs, links |
| Auto-detect ../boring-ui | If sibling dir exists, use it. Zero config for dev |
| Per-project .venv | Isolates child apps. Two apps can run simultaneously |
| node_modules symlink | `boring-ui` symlinked into node_modules — IDEs, TS, ESLint all work |
| Hermetic deploy build | `vite build` + `pip install` happen inside the image, not locally |
| GITHUB_TOKEN for deploy | Injected as build arg for private repo clone |
| .env for local dev | Secrets via `.env` file in dev — no Vault dependency |
| Dirty tree warning | `bui deploy` warns if ../boring-ui HEAD != pinned commit |
| TOML config | Human-readable, comments, single file for everything |
| Config → JSON (not codegen) | Avoid injection risk. Serve as JSON blob |
| `bui neon setup` prints, doesn't write | Avoids destroying TOML comments/formatting |

## Reviewer Feedback Incorporated

| Source | Feedback | Resolution |
|---|---|---|
| Gemini | "Go CLI = distribution hell" | Rejected: `go build && cp` is trivial |
| Gemini | "npm link is flaky (dual React)" | Fixed: symlink entire repo into node_modules, React externalized |
| Gemini | "Frontend aliasing undefined" | Fixed: node_modules/boring-ui symlink — IDEs/TS/ESLint work |
| Gemini | "Build should be hermetic" | Fixed: vite build + pip install inside deploy image |
| Gemini | "Private repo needs deploy key" | Fixed: GITHUB_TOKEN in [deploy.secrets], injected as build arg |
| Gemini | "Dirty tree footgun" | Fixed: bui deploy warns if local HEAD != pinned commit |
| Gemini | "No local dev secrets story" | Fixed: .env file support in bui dev |
| o3 | "Venv isolation needed" | Fixed: per-project .venv created by bui dev |
| o3 | "3 TOML parsers will drift" | Only Go + Python parse TOML. Frontend gets JSON |
| o3 | "Version coupling pip+npm" | Eliminated: bui manages boring-ui, not pip/npm |
| o3 | "Config → JS codegen injection risk" | Fixed: serve as JSON blob |
| o3 | "CI story missing" | Fixed: CI section added — clone side-by-side, same as local |
| o3 | "Build/deploy mismatch" | Fixed: hermetic build inside image |
| o3 | "Panel name collisions" | Namespace validation in config loader |
| Both | "Self-hosting test" | Kept: boring-ui boots from its own boring.app.toml |
