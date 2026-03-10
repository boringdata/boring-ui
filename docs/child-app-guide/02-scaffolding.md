# 2. Project Scaffolding

[< Back to Index](README.md) | [Prev: Architecture](01-architecture.md) | [Next: Backend >](03-backend.md)

---

## Directory Structure

```
my-app/
├── .gitmodules                    # boring-ui submodule
├── CLAUDE.md                      # Agent instructions
├── AGENTS.md                      # Safety rules & index
│
├── interface/
│   └── boring-ui/                 # Submodule (git)
│
├── src/web/
│   ├── .env                       # Local env vars (gitignored)
│   ├── .env.example               # Env var template (committed)
│   ├── index.html                 # SPA entry point
│   ├── package.json               # Frontend deps
│   ├── vite.config.js             # Vite bundler config
│   │
│   ├── backend/                   # Python backend
│   │   ├── __init__.py
│   │   ├── app.py                 # App factory (wraps boring-ui)
│   │   ├── config.py              # App-specific config resolution
│   │   ├── runtime.py             # Production ASGI wrapper
│   │   └── modules/               # Domain-specific routers
│   │       └── your_domain/
│   │           ├── __init__.py
│   │           ├── router.py      # FastAPI endpoints
│   │           └── service.py     # Business logic
│   │
│   └── frontend/                  # React frontend
│       ├── main.jsx               # App bootstrap
│       ├── app.config.js          # boring-ui config overrides
│       ├── mode.js                # Mode detection (optional)
│       ├── registry.js            # Pane registrations
│       ├── panels/                # Custom panel components
│       │   ├── MyPanel.jsx
│       │   └── MyPanel.css
│       ├── components/            # Shared components
│       ├── hooks/                 # Custom hooks
│       ├── services/              # API client services
│       └── styles/                # CSS
│
├── deploy/
│   ├── core/
│   │   ├── deploy.sh              # Core mode deploy script
│   │   ├── deploy.env             # Deploy config
│   │   └── modal_app.py           # Modal ASGI entrypoint
│   ├── edge/
│   │   ├── deploy.sh              # Edge mode deploy script
│   │   ├── deploy.env             # Deploy config
│   │   └── my-app.app.toml        # App config for boring-sandbox
│   └── shared/
│       └── _deploy_common.sh      # Shared bash helpers
│
├── scripts/
│   ├── build_web_wheel.sh         # Wheel builder
│   └── smoke_test.sh              # Integration tests
│
├── pyproject.toml                 # Python packaging
├── Cargo.toml                     # (Optional) Rust CLI
└── data/                          # Local data (gitignored)
```

## Step 1: Initialize the Repository

```bash
mkdir my-app && cd my-app
git init

# Add boring-ui as a submodule
git submodule add https://github.com/boringdata/boring-ui.git interface/boring-ui
git submodule update --init --recursive

# Create .gitignore
cat > .gitignore << 'EOF'
node_modules/
dist/
dist-front/
.env
.env.local
.venv/
__pycache__/
*.pyc
*.whl
data/
test-results/
*.egg-info/
EOF
```

## Step 2: Create `src/web/index.html`

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>My App</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="./frontend/main.jsx"></script>
  </body>
</html>
```

## Step 3: Create `src/web/package.json`

```json
{
  "name": "my-app-web",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 0.0.0.0",
    "build": "vite build",
    "backend": "PYTHONPATH=\"../../interface/boring-ui/src/back:../../src/web\" ../../.venv/bin/python -m uvicorn backend.app:app --reload --port 8000 --host 0.0.0.0 --ws wsproto",
    "dev:full": "concurrently \"npm:backend\" \"npm:dev\""
  },
  "dependencies": {
    "boring-ui": "file:../../interface/boring-ui",
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.0",
    "concurrently": "^9.0.0",
    "vite": "^6.0.0"
  },
  "engines": {
    "node": ">=18"
  }
}
```

**Key details:**
- `"boring-ui": "file:../../interface/boring-ui"` links to the submodule via npm's local file protocol
- React version must match boring-ui's peer dependency (`^18.2.0`); if you use React 19, add `dedupe: ['react', 'react-dom']` in `vite.config.js` to avoid version conflicts
- `--ws wsproto` is required for WebSocket support (without it, WebSocket bridging may fail)
- `--host 0.0.0.0` makes the backend accessible from remote VMs
- The `backend` script uses `.venv/bin/python` — see Step 5 for venv setup

## Step 4: Create `src/web/.env.example`

```bash
# Backend proxy target (dev server)
# BM_WEB_API_PROXY_TARGET=http://localhost:8000

# Your domain-specific env vars
# MY_APP_DATABASE_URL=postgresql://...

# Auth / Control Plane
# CONTROL_PLANE_ENABLED=false          # Disable auth entirely for local dev
# CONTROL_PLANE_PROVIDER=local         # local | neon | supabase
# BM_DEV_AUTO_SESSION=true             # Auto-create dev session (no login needed)
# BM_DEV_SESSION_USER_ID=local-dev
# BM_DEV_SESSION_EMAIL=dev@example.com

# Neon Auth (production — recommended)
# DATABASE_URL=postgresql://neondb_owner:...@ep-xxx-pooler.region.aws.neon.tech/neondb?sslmode=require
# NEON_AUTH_BASE_URL=https://ep-xxx.neonauth.region.aws.neon.tech/neondb/auth
# NEON_AUTH_JWKS_URL=https://ep-xxx.neonauth.region.aws.neon.tech/neondb/auth/.well-known/jwks.json

# Supabase (legacy)
# SUPABASE_URL=https://xxx.supabase.co
# SUPABASE_ANON_KEY=eyJ...
# SUPABASE_SERVICE_ROLE_KEY=eyJ...
# SUPABASE_DB_URL=postgresql://...

# Session (production: set a stable secret!)
# BORING_UI_SESSION_SECRET=your-secret-here
```

## Step 5: Install Dependencies

```bash
# Python backend dependencies
cd my-app
python3 -m venv .venv
source .venv/bin/activate

# Install boring-ui's backend deps + your app deps
pip install fastapi uvicorn[standard] httpx websockets python-dotenv \
  asyncpg "PyJWT[crypto]" ptyprocess wsproto

# If you have a pyproject.toml:
# pip install -e ".[web]"

# Frontend dependencies
cd src/web
npm install
```

**Why a venv?** The `backend` npm script uses `../../.venv/bin/python` to run uvicorn. Without the venv, `npm run dev:full` fails immediately.

**PYTHONPATH:** The backend needs two paths on PYTHONPATH:
- `../../interface/boring-ui/src/back` — for `import boring_ui`
- `../../src/web` — for `import backend`

This is set automatically by the `backend` npm script. For running tests or scripts directly, set it manually:
```bash
export PYTHONPATH="interface/boring-ui/src/back:src/web"
```

## Step 6: Create Backend Skeleton

```bash
mkdir -p src/web/backend/modules/my_domain
touch src/web/backend/__init__.py
touch src/web/backend/modules/__init__.py
touch src/web/backend/modules/my_domain/__init__.py
```

Then create `app.py`, `config.py`, `runtime.py` — see [Backend Integration](03-backend.md).

## Step 7: Create Frontend Skeleton

```bash
mkdir -p src/web/frontend/panels
```

Then create `main.jsx`, `app.config.js`, `registry.js` — see [Frontend Integration](04-frontend.md).
